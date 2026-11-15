"""Debug adapter session: launches a Python script under debugpy and drives
it over the Debug Adapter Protocol (DAP) on a localhost socket.

The VR client never speaks DAP — jarvis_server exposes simple HTTP routes
that start/control/poll a DebugSession. One session exists per workspace
session id; starting a second one stops the first.
"""
import json
import queue
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

_IDLE_SECONDS = 600          # kill the debuggee after this much quiet time
_MAX_OUTPUT_LINES = 400
_MAX_OUTPUT_LINE = 500
_MAX_VARIABLES = 100
_MAX_VALUE_LEN = 300


def _scrubbed_env():
    """Same credential scrub /workspace/run applies to child processes."""
    import os
    return {k: v for k, v in os.environ.items()
            if not any(s in k.upper() for s in ('KEY', 'TOKEN', 'SECRET', 'PASSWORD'))}


class DapClient:
    """Content-Length framed DAP peer. A reader thread dispatches responses
    to waiting request() calls and events to on_event."""

    def __init__(self, port, on_event=None, connect_timeout=20):
        deadline = time.time() + connect_timeout
        while True:
            try:
                self.sock = socket.create_connection(('127.0.0.1', port), timeout=15)
                break
            except OSError:
                if time.time() >= deadline:
                    raise
                time.sleep(0.2)
        self.sock.settimeout(None)
        self.seq = 0
        self.buf = b''
        self.events = []
        self._pending = {}
        self._pending_lock = threading.Lock()
        self._on_event = on_event
        self._closed = False
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def send(self, command, arguments=None):
        self.seq += 1
        data = json.dumps({'seq': self.seq, 'type': 'request',
                           'command': command, 'arguments': arguments or {}}).encode()
        self.sock.sendall(b'Content-Length: %d\r\n\r\n' % len(data) + data)
        return self.seq

    def request(self, command, arguments=None, timeout=15):
        seq = self.send(command, arguments)
        q = queue.Queue(maxsize=1)
        with self._pending_lock:
            self._pending[seq] = q
        try:
            msg = q.get(timeout=timeout)
        finally:
            with self._pending_lock:
                self._pending.pop(seq, None)
        if msg.get('type') == 'response' and not msg.get('success', True):
            raise RuntimeError('%s failed: %s' % (command, msg.get('message', '?')))
        return msg

    def _read(self):
        while b'\r\n\r\n' not in self.buf:
            c = self.sock.recv(65536)
            if not c:
                raise EOFError
            self.buf += c
        head, rest = self.buf.split(b'\r\n\r\n', 1)
        m = re.search(rb'Content-Length: (\d+)', head)
        if not m:
            raise ValueError('bad DAP header')
        n = int(m.group(1))
        while len(rest) < n:
            c = self.sock.recv(65536)
            if not c:
                raise EOFError
            rest += c
        self.buf = rest[n:]
        return json.loads(rest[:n])

    def _read_loop(self):
        try:
            while not self._closed:
                msg = self._read()
                if msg.get('type') == 'event':
                    self.events.append(msg)
                    cb = self._on_event
                    if cb:
                        try:
                            cb(msg)
                        except Exception:
                            pass
                elif msg.get('type') == 'response':
                    with self._pending_lock:
                        q = self._pending.get(msg.get('request_seq'))
                    if q is not None:
                        try:
                            q.put_nowait(msg)
                        except queue.Full:
                            pass
        except (EOFError, OSError, ValueError):
            pass
        finally:
            with self._pending_lock:
                for q in self._pending.values():
                    try:
                        q.put_nowait({'type': 'response', 'success': False,
                                      'message': 'debug adapter closed'})
                    except queue.Full:
                        pass

    def close(self):
        self._closed = True
        try:
            self.sock.close()
        except OSError:
            pass


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


class DebugSession:
    """One debugpy debuggee. status: starting/running/stopped/exited/error."""

    def __init__(self, wt, script, args, breakpoints):
        self.wt = Path(wt)
        self.script = script
        self.args = list(args or [])
        self.breakpoints = list(breakpoints or [])
        self.status = 'starting'
        self.file = ''
        self.line = 0
        self.variables = []
        self.output = []
        self.error = ''
        self.proc = None
        self.dap = None
        self._thread_id = None
        self._dap_lock = threading.Lock()
        self._finished = threading.Event()
        self.last_activity = time.time()
        self._stdout_thread = None
        self._watchdog = None
        self._start()

    # ---------------------------------------------------------- lifecycle

    def _start(self):
        port = _free_port()
        cmd = [sys.executable, '-m', 'debugpy', '--listen',
               '127.0.0.1:%d' % port, '--wait-for-client',
               self.script] + self.args
        try:
            self.proc = subprocess.Popen(
                cmd, cwd=str(self.wt), env=_scrubbed_env(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, errors='replace')
        except OSError as exc:
            self.status = 'error'
            self.error = str(exc)[:300]
            self._finished.set()
            return
        self._stdout_thread = threading.Thread(target=self._pump_output,
                                               daemon=True)
        self._stdout_thread.start()
        self._watchdog = threading.Thread(target=self._idle_watch, daemon=True)
        self._watchdog.start()
        threading.Thread(target=self._dap_handshake, args=(port,),
                         daemon=True).start()

    def _idle_watch(self):
        while not self._finished.is_set():
            time.sleep(min(15, max(1, _IDLE_SECONDS / 4)))
            if time.time() - self.last_activity > _IDLE_SECONDS:
                self.stop()
                return

    def _pump_output(self):
        try:
            for line in self.proc.stdout:
                self._append_output(line.rstrip('\n'))
        except (OSError, ValueError):
            pass
        self._append_output('[process exited]')

    def _append_output(self, line):
        line = (line or '')[:_MAX_OUTPUT_LINE]
        self.output.append(line)
        if len(self.output) > _MAX_OUTPUT_LINES:
            del self.output[:len(self.output) - _MAX_OUTPUT_LINES]

    def _touch(self):
        self.last_activity = time.time()

    def _dap_handshake(self, port):
        try:
            self.dap = DapClient(port, on_event=self._on_event)
            self.dap.request('initialize', {
                'adapterID': 'jarvis',
                'clientID': 'jarvis-vr',
                'linesStartAt1': True,
                'columnsStartAt1': True,
                'pathFormat': 'path',
            }, timeout=20)
            # debugpy rejects an attach with empty arguments, and answers the
            # attach response only after configurationDone — fire it without
            # waiting and sync on the 'initialized' event instead.
            self.dap.send('attach', {'justMyCode': True})
            deadline = time.time() + 20
            while time.time() < deadline:
                if any(e.get('event') == 'initialized' for e in self.dap.events):
                    break
                time.sleep(0.05)
            else:
                raise TimeoutError('no initialized event')
            for bp in self.breakpoints:
                bpath = str((self.wt / bp['path']).resolve()) \
                    if not Path(bp['path']).is_absolute() else bp['path']
                self.dap.request('setBreakpoints', {
                    'source': {'path': bpath},
                    'breakpoints': [{'line': int(bp.get('line', 1))}],
                }, timeout=10)
            self.dap.request('configurationDone', {}, timeout=10)
            self.status = 'running'
        except Exception as exc:
            self.status = 'error'
            self.error = str(exc)[:300]
            self.stop()

    # ---------------------------------------------------------- events

    def _on_event(self, ev):
        self._touch()
        kind = ev.get('event')
        if kind == 'output':
            body = ev.get('body') or {}
            if body.get('category') in (None, 'stdout', 'stderr'):
                self._append_output(str(body.get('output', '')))
        elif kind == 'stopped':
            body = ev.get('body') or {}
            self._thread_id = body.get('threadId')
            threading.Thread(target=self._capture_stop,
                             daemon=True).start()
        elif kind in ('terminated', 'exited'):
            self.status = 'exited'
            self._thread_id = None
            self.variables = []
            self._finished.set()

    def _capture_stop(self):
        """Fetch the paused location and top-frame variables. Serialized with
        control requests through _dap_lock so DAP traffic never interleaves."""
        try:
            with self._dap_lock:
                if self.dap is None:
                    return
                threads = self.dap.request('threads', {}, timeout=10)
                tid = self._thread_id
                if tid is None and threads.get('body', {}).get('threads'):
                    tid = threads['body']['threads'][0].get('id')
                self._thread_id = tid
                if tid is None:
                    return
                st = self.dap.request('stackTrace', {
                    'threadId': tid, 'startFrame': 0, 'levels': 1}, timeout=10)
                frames = st.get('body', {}).get('stackFrames') or []
                if not frames:
                    return
                frame = frames[0]
                self.file = frame.get('source', {}).get('path', '')
                try:
                    self.file = str(Path(self.file).resolve()
                                    .relative_to(self.wt.resolve()))
                except (ValueError, OSError):
                    pass
                self.line = frame.get('line', 0)
                scopes = self.dap.request('scopes', {
                    'frameId': frame.get('id')}, timeout=10)
                self.variables = []
                for scope in (scopes.get('body', {}).get('scopes') or [])[:4]:
                    try:
                        vs = self.dap.request('variables', {
                            'variablesReference': scope.get('variablesReference'),
                            'filter': 'named'}, timeout=10)
                    except Exception:
                        continue
                    for v in (vs.get('body', {}).get('variables') or []):
                        if len(self.variables) >= _MAX_VARIABLES:
                            break
                        val = str(v.get('value', ''))[:_MAX_VALUE_LEN]
                        self.variables.append(
                            {'name': str(v.get('name', ''))[:100], 'value': val})
                self.status = 'stopped'
        except Exception:
            pass

    # ---------------------------------------------------------- control

    def _request(self, command, arguments=None, timeout=10):
        self._touch()
        with self._dap_lock:
            if self.dap is None:
                raise RuntimeError('debug session is not connected')
            return self.dap.request(command, arguments, timeout=timeout)

    def cont(self):
        if self._thread_id is not None:
            self._request('continue', {'threadId': self._thread_id})
        self.status = 'running'
        self.variables = []

    def step(self, command):
        if self._thread_id is not None:
            self._request(command, {'threadId': self._thread_id})
        self.status = 'running'

    def stop(self):
        if self._finished.is_set():
            return
        try:
            if self.dap is not None:
                with self._dap_lock:
                    try:
                        self.dap.request('disconnect',
                                         {'terminateDebuggee': True}, timeout=5)
                    except Exception:
                        pass
        finally:
            try:
                if self.dap is not None:
                    self.dap.close()
            except Exception:
                pass
            try:
                if self.proc is not None and self.proc.poll() is None:
                    self.proc.kill()
                    self.proc.wait(timeout=5)
            except Exception:
                pass
            self.status = 'exited'
            self._finished.set()

    @property
    def finished(self):
        return self._finished.is_set()

    def snapshot(self):
        return {'status': self.status, 'file': self.file, 'line': self.line,
                'variables': list(self.variables),
                'output': list(self.output[-_MAX_OUTPUT_LINES:]),
                'error': self.error}
