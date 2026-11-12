"""Trace session manager: spawns trace_worker subprocesses, enforces
timeouts, stores per-session state and derives call edges from events."""
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

_SESSIONS: dict = {}          # trace_id -> session dict (per server process)
TRACE_ROOT = Path(tempfile.gettempdir()) / 'jarvis_traces'


def start(worktree: str, command: list, timeout_s: int = 30,
          max_events: int = 20000) -> dict:
    wt = Path(worktree).resolve()
    script = (wt / command[0]).resolve()
    script.relative_to(wt)              # raises ValueError if it escapes
    trace_id = 'trace_' + uuid.uuid4().hex[:12]
    d = TRACE_ROOT / trace_id
    d.mkdir(parents=True)
    out = d / 'events.jsonl'
    proc = subprocess.Popen(            # list argv, shell=False
        [sys.executable, '-m', 'ai_agents.runtime.trace_worker',
         '--root', str(wt), '--out', str(out),
         '--max-events', str(max_events),
         '--', str(script), *command[1:]],
        cwd=str(wt), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        env={'PATH': os.environ.get('PATH', ''),
             'PYTHONPATH': str(Path(__file__).parents[2])},
        start_new_session=True)
    _SESSIONS[trace_id] = {'proc': proc, 'out': out, 'worktree': str(wt),
                           'deadline': time.time() + timeout_s,
                           'status': 'running'}
    return {'trace_id': trace_id, 'status': 'running'}


def _refresh(s):
    if s['status'] != 'running':
        return
    rc = s['proc'].poll()
    if rc is None and time.time() > s['deadline']:
        os.killpg(s['proc'].pid, signal.SIGKILL)
        s['proc'].wait()
        s['status'] = 'timed_out'
    elif rc is not None:
        s['status'] = 'completed' if rc == 0 else 'failed'


def stop(trace_id: str) -> dict:
    s = _SESSIONS.get(trace_id)
    if not s:
        return {'status': 'not_found'}
    if s['proc'].poll() is None:
        os.killpg(s['proc'].pid, signal.SIGTERM)
        try:
            s['proc'].wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(s['proc'].pid, signal.SIGKILL)
        s['status'] = 'stopped'
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
        for line in s['out'].read_text(encoding='utf-8').splitlines():
            rec = json.loads(line)
            (end.update(rec) if rec.get('kind') == '_end'
             else events.append(rec))
    edges, stack = [], []
    for ev in events:                       # derive runtime call relationships
        if ev['kind'] == 'call':
            if stack:
                edges.append({'source': stack[-1],
                              'target': ev['function']})
            stack.append(ev['function'])
        elif ev['kind'] == 'return' and stack:
            stack.pop()
    uniq = [dict(t) for t in {tuple(sorted(e.items())) for e in edges}]
    return {'status': s['status'], 'trace_id': trace_id, 'events': events,
            'call_edges': uniq, 'exit_code': end.get('exit_code'),
            'truncated': bool(end.get('truncated'))}
