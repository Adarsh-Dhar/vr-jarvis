"""Trace session manager: spawns trace_worker subprocesses, enforces
timeouts, stores per-session state and derives call edges from events."""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

_SESSIONS: dict = {}          # trace_id -> session dict (per server process)
TRACE_ROOT = Path(tempfile.gettempdir()) / 'jarvis_traces'
STOP_GRACE_S = 3
TRACE_TTL_S = 900              # finished traces are kept for 15 minutes


def make_snapshot(src: str, ignore) -> str:
    """Copy a working tree (minus ignored names) so a trace can run against
    the repository even when no sandbox worktree exists. Returns the path of
    the copied 'repo' directory; the caller owns the tempdir parent."""
    dst = Path(tempfile.mkdtemp(prefix='jarvis_snap_'))
    shutil.copytree(src, dst / 'repo', ignore=ignore, symlinks=False,
                    dirs_exist_ok=True)
    return str(dst / 'repo')


def cleanup_expired():
    """Drop finished traces (and their snapshots) older than TRACE_TTL_S."""
    now = time.time()
    for tid, s in list(_SESSIONS.items()):
        _refresh(s)
        if s['status'] != 'running' \
                and now - s.get('finished_at', now) > TRACE_TTL_S:
            if s.get('snapshot'):
                shutil.rmtree(Path(s['snapshot']).parent, ignore_errors=True)
            shutil.rmtree(TRACE_ROOT / tid, ignore_errors=True)
            _SESSIONS.pop(tid, None)


def _terminate(s, sig=signal.SIGTERM):
    try:
        os.killpg(s['proc'].pid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def _stop_gracefully(s):
    """SIGTERM the process group, wait STOP_GRACE_S, SIGKILL on timeout and
    append a terminal '_end' record so readers always see one."""
    if s['proc'].poll() is not None:
        return
    _terminate(s, signal.SIGTERM)
    try:
        s['proc'].wait(timeout=STOP_GRACE_S)
    except subprocess.TimeoutExpired:
        _terminate(s, signal.SIGKILL)
        try:
            s['proc'].wait(timeout=STOP_GRACE_S)
        except subprocess.TimeoutExpired:
            pass
        try:
            with open(s['out'], 'a', encoding='utf-8') as f:
                f.write(json.dumps({'kind': '_end', 'status': 'killed',
                                    'exit_code': None, 'truncated': False})
                        + '\n')
        except Exception:
            pass


def start(worktree: str, command: list, timeout_s: int = 30,
          max_events: int = 20000, snapshot: str = None) -> dict:
    cleanup_expired()
    wt = Path(worktree).resolve()
    script = (wt / command[0]).resolve()
    script.relative_to(wt)              # raises ValueError if it escapes
    trace_id = 'trace_' + uuid.uuid4().hex[:12]
    d = TRACE_ROOT / trace_id
    d.mkdir(parents=True)
    out = d / 'events.jsonl'
    err_path = d / 'stderr.txt'
    err_f = open(err_path, 'wb')
    proc = subprocess.Popen(            # list argv, shell=False
        [sys.executable, '-m', 'ai_agents.runtime.trace_worker',
         '--root', str(wt), '--out', str(out),
         '--max-events', str(max_events),
         '--', str(script), *command[1:]],
        cwd=str(wt), stdout=subprocess.DEVNULL, stderr=err_f,
        env={'PATH': os.environ.get('PATH', ''),
             'PYTHONPATH': str(Path(__file__).parents[2])},
        start_new_session=True)
    err_f.close()                       # the child keeps its own handle
    _SESSIONS[trace_id] = {'proc': proc, 'out': out, 'worktree': str(wt),
                           'stderr': err_path, 'snapshot': snapshot,
                           'deadline': time.time() + timeout_s,
                           'status': 'running', 'finished_at': None}
    return {'trace_id': trace_id, 'status': 'running'}


def _refresh(s):
    if s['status'] != 'running':
        return
    rc = s['proc'].poll()
    if rc is None and time.time() > s['deadline']:
        _stop_gracefully(s)
        s['proc'].wait()
        s['status'] = 'timed_out'
        s['finished_at'] = time.time()
    elif rc is not None:
        s['status'] = 'completed' if rc == 0 else 'failed'
        s['finished_at'] = time.time()


def stop(trace_id: str) -> dict:
    s = _SESSIONS.get(trace_id)
    if not s:
        return {'status': 'not_found'}
    if s['proc'].poll() is None:
        _stop_gracefully(s)
        s['status'] = 'stopped'
        s['finished_at'] = time.time()
    else:
        _refresh(s)
    return {'trace_id': trace_id, 'status': s['status']}


def get(trace_id: str) -> dict:
    s = _SESSIONS.get(trace_id)
    if not s:
        return {'status': 'not_found'}
    _refresh(s)
    events, end = [], {}
    if s['out'].exists():
        text = s['out'].read_text(encoding='utf-8')
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                if s['status'] == 'running':
                    break              # incomplete final line, still being written
                raise
            (end.update(rec) if rec.get('kind') == '_end'
             else events.append(rec))
    # Per-thread call stacks: edges are derived within each thread only.
    stacks, edges = {}, []
    for ev in events:
        stack = stacks.setdefault(ev.get('thread_id', 0), [])
        if ev['kind'] == 'call':
            if stack:
                edges.append({'source': stack[-1]['function'],
                              'target': ev['function']})
            stack.append({'function': ev['function'],
                          'frame_id': ev.get('frame_id')})
        elif ev['kind'] == 'return' and stack:
            fid = ev.get('frame_id')
            while stack:                       # pops to the matching frame; recursion-safe
                top = stack.pop()
                if fid is None or top['frame_id'] == fid:
                    break
    uniq = [dict(t) for t in {tuple(sorted(e.items())) for e in edges}]
    stderr_tail = ''
    try:
        err = s.get('stderr')
        if err and Path(err).exists():
            stderr_tail = Path(err).read_bytes()[-2000:].decode(
                'utf-8', 'replace')
    except Exception:
        pass
    return {'status': s['status'], 'trace_id': trace_id, 'events': events,
            'call_edges': uniq, 'exit_code': end.get('exit_code'),
            'truncated': bool(end.get('truncated')),
            'stderr_tail': stderr_tail}
