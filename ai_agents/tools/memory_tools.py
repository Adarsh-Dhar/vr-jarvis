import json
import os
import tempfile
import threading
from datetime import datetime, timezone

from google.adk.tools import ToolContext

from ..config import MEMORY_PATH
from ._safe import safe

_LOCK = threading.Lock()


def _load():
    if MEMORY_PATH.exists():
        return json.loads(MEMORY_PATH.read_text())
    return {'findings': [], 'decisions': [], 'last_session': None}


def _save(data):
    '''Write atomically so a crash or a concurrent reader never sees half a file.'''
    fd, tmp = tempfile.mkstemp(dir=str(MEMORY_PATH.parent), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, MEMORY_PATH)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


@safe
def load_project_memory(tool_context: ToolContext) -> dict:
    '''Return saved findings, decisions and the last session summary for this project.'''
    return {'status': 'ok', **_load()}


@safe
def save_finding(summary: str, node_ids: list[str], tool_context: ToolContext) -> dict:
    '''Save an investigation finding with the node ids that support it.'''
    with _LOCK:
        data = _load()
        data['findings'].append({'at': _now(), 'summary': summary, 'node_ids': node_ids})
        _save(data)
    return {'status': 'ok'}


@safe
def record_decision(decision: str, tool_context: ToolContext) -> dict:
    '''Record a decision the user approved or rejected.'''
    with _LOCK:
        data = _load()
        data['decisions'].append({'at': _now(), 'decision': decision})
        _save(data)
    return {'status': 'ok'}
