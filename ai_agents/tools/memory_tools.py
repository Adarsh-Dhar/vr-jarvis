import json
from datetime import datetime, timezone

from google.adk.tools import ToolContext

from ..config import MEMORY_PATH


def _load():
    if MEMORY_PATH.exists():
        return json.loads(MEMORY_PATH.read_text())
    return {'findings': [], 'decisions': [], 'last_session': None}


def _save(data):
    MEMORY_PATH.write_text(json.dumps(data, indent=2))


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def load_project_memory(tool_context: ToolContext) -> dict:
    '''Return saved findings, decisions and the last session summary for this project.'''
    return {'status': 'ok', **_load()}


def save_finding(summary: str, node_ids: list[str], tool_context: ToolContext) -> dict:
    '''Save an investigation finding with the node ids that support it.'''
    data = _load()
    data['findings'].append({'at': _now(), 'summary': summary, 'node_ids': node_ids})
    _save(data)
    return {'status': 'ok'}


def record_decision(decision: str, tool_context: ToolContext) -> dict:
    '''Record a decision the user approved or rejected.'''
    data = _load()
    data['decisions'].append({'at': _now(), 'decision': decision})
    _save(data)
    return {'status': 'ok'}
