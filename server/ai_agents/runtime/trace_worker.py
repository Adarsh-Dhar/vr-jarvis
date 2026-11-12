"""Trace worker: runs inside the traced subprocess.

Usage: python -m ai_agents.runtime.trace_worker --root <worktree>
       --out <events.jsonl> --max-events N -- <script> [args...]

Installs a tracer, runs the target with runpy and writes one JSON line per
event. Only names and locations are recorded; frames outside the worktree
(stdlib, site-packages) are ignored so no third-party values can reach the
trace file.
"""
import argparse
import json
import os
import runpy
import sys
import threading
import time


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--max-events', type=int, default=20000)
    p.add_argument('target', nargs=argparse.REMAINDER)
    a = p.parse_args()
    target = [t for t in a.target if t != '--']
    root = os.path.realpath(a.root)
    out = open(a.out, 'w', encoding='utf-8')
    seq = 0
    truncated = False
    lock = threading.Lock()

    def rel(path):
        if not path or path.startswith('<'):
            return None
        rp = os.path.realpath(path)
        return os.path.relpath(rp, root) if rp.startswith(root + os.sep) else None

    def emit(kind, frame, exc=None):
        nonlocal seq, truncated
        f = rel(frame.f_code.co_filename)
        if f is None:                      # stdlib / site-packages / outside root
            return
        with lock:
            if seq >= a.max_events:
                truncated = True
                return
            seq += 1
            ev = {'sequence': seq, 'kind': kind,
                  'function': frame.f_code.co_qualname
                  if hasattr(frame.f_code, 'co_qualname')
                  else frame.f_code.co_name,
                  'module': frame.f_globals.get('__name__'),
                  'file': f, 'line': frame.f_lineno, 'ts': time.time()}
            if exc is not None:
                ev['exception_type'] = exc.__name__     # type name only
            out.write(json.dumps(ev) + '\n')

    def tracer(frame, event, arg):
        if event == 'call':
            emit('call', frame)
            return tracer
        if event == 'return':
            emit('return', frame)
        elif event == 'exception':
            emit('exception', frame, exc=arg[0])
        return tracer

    status, exit_code = 'completed', 0
    sys.path.insert(0, root)
    os.chdir(root)
    sys.argv = target
    sys.settrace(tracer)
    threading.settrace(tracer)
    try:
        runpy.run_path(target[0], run_name='__main__')
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) \
            else (0 if e.code is None else 1)
    except BaseException:
        status, exit_code = 'failed', 1
    finally:
        sys.settrace(None)
        threading.settrace(None)
        out.write(json.dumps({'kind': '_end', 'status': status,
                              'exit_code': exit_code,
                              'truncated': truncated}) + '\n')
        out.close()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
