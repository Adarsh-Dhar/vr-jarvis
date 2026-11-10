"""
Architecture design tools.

Structured idea -> requirements -> proposed architecture -> repository
comparison -> implementation plan. Model output only ever *proposes*: the
session state keeps status='draft' until a human approves through the API,
and an approved architecture reverts to draft on any edit.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.adk.tools import ToolContext

from .. import config

log = logging.getLogger(__name__)

REQUIREMENT_KEYS = ('goals', 'functional', 'non_functional', 'constraints', 'assumptions', 'open_questions')
ARCH_VERSION = 3
DESIGN_DIR = config.ROOT / 'data' / 'design'


def _blank_requirements() -> Dict[str, List[str]]:
    return {k: [] for k in REQUIREMENT_KEYS}


def _blank_architecture() -> Dict[str, Any]:
    return {'version': ARCH_VERSION, 'status': 'draft', 'components': [], 'relationships': [],
            'approved_by': '', 'approved_version': 0}


def _norm(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', (s or '').lower())


def _sentences(text: str) -> List[str]:
    parts = re.split(r'(?<=[.!?])\s+|\n+', (text or '').strip())
    return [p.strip(' -•\t') for p in parts if p and p.strip(' -•\t')]


def _llm_json(system: str, user: str, fallback):
    """Ask the model for a JSON object. Falls back to `fallback()` when there is
    no API key, the call fails, or the reply is not valid JSON."""
    try:
        from google import genai
        client = genai.Client()   # reads GOOGLE_API_KEY / Vertex settings from the environment
        resp = client.models.generate_content(
            model=config.MODEL_NAME,
            contents=[system + '\n\n' + user],
            config={'response_mime_type': 'application/json'},
        )
        data = json.loads(resp.text or '{}')
        if isinstance(data, dict):
            return data
    except Exception as exc:
        log.warning('architecture LLM call failed, using heuristic fallback: %s', exc)
    return fallback()


# ---------------------------------------------------------------------------
# Tools (also callable directly by the /design endpoints)


def extract_requirements(idea_text: str, tool_context: ToolContext = None) -> dict:
    """Turn a raw idea into structured requirements.

    Returns {goals, functional, non_functional, constraints, assumptions,
    open_questions} — each a list of strings.
    """
    def heuristic():
        req = _blank_requirements()
        sents = _sentences(idea_text)
        req['goals'] = sents[:1] or [idea_text.strip()]
        req['functional'] = sents[1:] if len(sents) > 1 else []
        return req

    data = _llm_json(
        'You extract software requirements from a developer idea. '
        'Reply with JSON only: {"goals": [...], "functional": [...], '
        '"non_functional": [...], "constraints": [...], "assumptions": [...], '
        '"open_questions": [...]}. Each list contains short strings.',
        'Idea: ' + (idea_text or ''),
        heuristic,
    )
    req = _blank_requirements()
    for k in REQUIREMENT_KEYS:
        v = data.get(k)
        if isinstance(v, list):
            req[k] = [str(x) for x in v]
        elif isinstance(v, str) and v.strip():
            req[k] = [v.strip()]
    if not any(req.values()):
        req = heuristic()
    return {'status': 'ok', 'requirements': req}


def propose_architecture(requirements, tool_context: ToolContext = None) -> dict:
    """Propose a component architecture for a requirements document.

    `requirements` is the dict returned by extract_requirements (or the raw
    idea text). Returns {components, relationships} — never writes code.
    """
    if isinstance(requirements, str):
        req = extract_requirements(requirements)['requirements']
    elif isinstance(requirements, dict) and 'requirements' in requirements:
        req = requirements['requirements']
    elif isinstance(requirements, dict):
        req = {k: ([str(x) for x in v] if isinstance(v, list) else []) for k, v in requirements.items()}
        for k in REQUIREMENT_KEYS:
            req.setdefault(k, [])
    else:
        req = _blank_requirements()

    def heuristic():
        comps, rels = [], []
        # one component per functional requirement; fall back to goals, then a single core component
        sources = req.get('functional') or req.get('goals') or ['Core']
        for i, f in enumerate(sources, 1):
            cid = 'c%d' % i
            name = f.split(':')[0].strip()[:40] or 'Component %d' % i
            comps.append({'id': cid, 'name': name, 'responsibility': f,
                          'kind': 'service', 'requirement_ids': []})
        # chain the components so the plan has an order
        ids = [c['id'] for c in comps]
        for a, b in zip(ids, ids[1:]):
            rels.append({'id': 'e%d' % (len(rels) + 1), 'src': a, 'dst': b,
                         'kind': 'calls', 'label': ''})
        return {'components': comps, 'relationships': rels}

    data = _llm_json(
        'You are a software architect. Given requirements, propose a component '
        'architecture. Reply with JSON only: {"components": [{"id": "c1", '
        '"name": "...", "responsibility": "...", "kind": '
        '"service|library|ui|data|external", "requirement_ids": ["r1"]}], '
        '"relationships": [{"src": "c1", "dst": "c2", "kind": '
        '"calls|reads|publishes", "label": "..."}]}. '
        'Every relationship src/dst must be an existing component id.',
        'Requirements: ' + json.dumps(req)[:6000],
        heuristic,
    )

    comps = []
    for i, c in enumerate(data.get('components') or [], 1):
        if not isinstance(c, dict):
            continue
        comps.append({
            'id': str(c.get('id') or 'c%d' % i),
            'name': str(c.get('name') or 'Component %d' % i),
            'responsibility': str(c.get('responsibility') or ''),
            'kind': str(c.get('kind') or 'service'),
            'requirement_ids': [str(x) for x in (c.get('requirement_ids') or [])],
        })
    ids = {c['id'] for c in comps}
    rels = []
    for i, r in enumerate(data.get('relationships') or [], 1):
        if not isinstance(r, dict):
            continue
        src, dst = str(r.get('src') or ''), str(r.get('dst') or '')
        if src not in ids or dst not in ids or src == dst:
            continue   # drop dangling/self relationships instead of failing the proposal
        rels.append({'id': str(r.get('id') or 'e%d' % i), 'src': src, 'dst': dst,
                     'kind': str(r.get('kind') or 'calls'), 'label': str(r.get('label') or '')})
    if not comps:
        h = heuristic()
        comps, rels = h['components'], h['relationships']
    return {'status': 'ok', 'components': comps, 'relationships': rels}


def _graph_node_index():
    """Return {normalized_name: node} for the current repository graph."""
    index = {}
    try:
        path = config.GRAPH_PATH
        if not path.is_file():
            return index
        data = json.loads(path.read_text())
        for n in data.get('nodes', []):
            for key in (n.get('name'), n.get('id'), n.get('qualname')):
                if key:
                    index.setdefault(_norm(key), n)
    except Exception as exc:
        log.warning('compare_to_repository could not read graph: %s', exc)
    return index


def compare_to_repository(architecture, tool_context: ToolContext = None) -> dict:
    """Map each proposed component onto repository graph nodes.

    Returns {matched, missing, extra} where each entry carries the component
    (or node) id, name and the evidence used for the match.
    """
    arch = architecture.get('architecture', architecture) if isinstance(architecture, dict) else {}
    comps = arch.get('components') or []
    nodes = _graph_node_index()

    matched, missing = [], []
    used_nodes = set()
    for c in comps:
        cid, name = str(c.get('id')), str(c.get('name') or '')
        hit = nodes.get(_norm(name))
        if hit is None:   # fall back to containment either way
            nn = _norm(name)
            for k, n in nodes.items():
                if nn and (nn in k or k in nn):
                    hit = n
                    break
        if hit is not None:
            nid = hit.get('id') or hit.get('name')
            matched.append({'id': cid, 'name': name, 'node': nid,
                            'evidence': '%s (%s)' % (nid, hit.get('file') or '?')})
            used_nodes.add(nid)
        else:
            missing.append({'id': cid, 'name': name, 'node': '', 'evidence': 'no graph node matches'})

    extra = [{'id': n.get('id') or n.get('name'), 'name': n.get('name') or n.get('id'),
              'node': n.get('id'), 'evidence': n.get('file') or ''}
             for k, n in nodes.items()
             if (n.get('id') or n.get('name')) not in used_nodes
             and n.get('level') not in ('module', 'file')]
    return {'status': 'ok', 'matched': matched, 'missing': missing, 'extra': extra[:50]}


def generate_implementation_plan(architecture, tool_context: ToolContext = None) -> dict:
    """Turn an approved architecture into a dependency-ordered task list.

    Tasks are ordered so a component's task depends on the tasks of the
    components it calls/reads. Returns {tasks: [...]} with depends_on,
    component_id, acceptance and owner on every task.
    """
    arch = architecture.get('architecture', architecture) if isinstance(architecture, dict) else {}
    comps = arch.get('components') or []
    rels = arch.get('relationships') or []

    # dependency: src depends on dst (src calls/reads dst -> dst first)
    deps = {c['id']: set() for c in comps}
    for r in rels:
        src, dst = r.get('src'), r.get('dst')
        if src in deps and dst in deps and src != dst:
            deps[src].add(dst)

    # Kahn's algorithm: a component can be scheduled once every component it
    # depends on is already scheduled. Whatever remains has a circular
    # dependency — it is reported in `circular` instead of being silently
    # dropped from the ordering.
    remaining = {cid: set(d) for cid, d in deps.items()}
    order, ready = [], sorted(cid for cid, d in remaining.items() if not d)
    while ready:
        cid = ready.pop(0)
        if cid in order:
            continue
        order.append(cid)
        for other, ds in remaining.items():
            if cid in ds:
                ds.discard(cid)
                if not ds and other not in order and other not in ready:
                    ready.append(other)
        ready.sort()

    cyclic = sorted(cid for cid in remaining if cid not in order)
    cyclic_set = set(cyclic)
    order = order + cyclic   # cyclic components still get tasks, scheduled last

    task_of = {}
    tasks = []
    for i, cid in enumerate(order, 1):
        comp = next((c for c in comps if c['id'] == cid), None)
        if comp is None:
            continue
        tid = 't%d' % i
        task_of[cid] = tid
        # Only dependencies that are already scheduled produce valid task
        # edges; edges inside a cycle are dropped (reported via `circular`).
        depends = [d for d in sorted(deps.get(cid, ()))
                   if d in task_of and not (cid in cyclic_set and d in cyclic_set)]
        tasks.append({'id': tid, 'title': 'Implement ' + comp.get('name', cid),
                      'status': 'pending', 'component_id': cid,
                      'depends_on': [task_of[d] for d in depends],
                      'acceptance': comp.get('responsibility') or '',
                      'owner': 'developer'})

    return {'status': 'ok', 'tasks': tasks, 'circular': cyclic}


# ---------------------------------------------------------------------------
# Disk persistence (design docs survive server restarts)


def _design_path(session_id: str) -> Path:
    safe = re.sub(r'[^A-Za-z0-9_-]', '', session_id or '')
    return DESIGN_DIR / (safe + '.json')


def save_design(session_id: str, payload: Dict[str, Any]) -> None:
    try:
        DESIGN_DIR.mkdir(parents=True, exist_ok=True)
        _design_path(session_id).write_text(json.dumps(payload, indent=2, default=str))
    except Exception as exc:
        log.warning('could not persist design state for %s: %s', session_id, exc)


def load_design(session_id: str) -> Dict[str, Any]:
    try:
        p = _design_path(session_id)
        if p.is_file():
            return json.loads(p.read_text())
    except Exception as exc:
        log.warning('could not load design state for %s: %s', session_id, exc)
    return {}
