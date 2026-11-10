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

# Canonical vocabularies; model output outside these is normalised, not trusted.
COMPONENT_KINDS = ('service', 'library', 'ui', 'data', 'external')
RELATIONSHIP_KINDS = ('calls', 'reads', 'publishes')


def _blank_requirements() -> Dict[str, List[str]]:
    return {k: [] for k in REQUIREMENT_KEYS}


def _blank_architecture() -> Dict[str, Any]:
    return {'version': ARCH_VERSION, 'revision': 1, 'status': 'draft',
            'components': [], 'relationships': [],
            'approved_by': '', 'approved_version': 0, 'approved_revision': 0}


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
    id_map = {}   # model-supplied id -> canonical id (duplicates are renamed)
    used_ids = set()
    for i, c in enumerate(data.get('components') or [], 1):
        if not isinstance(c, dict):
            continue
        cid = str(c.get('id') or '').strip() or 'c%d' % i
        if cid in used_ids or cid in id_map.values():
            # Duplicate id: keep the component under a fresh canonical id and
            # remap relationship endpoints below.
            base = re.sub(r'[^A-Za-z0-9_.-]', '', cid)[:40] or 'c'
            cid = '%s_%d' % (base, i)
            while cid in used_ids:
                cid += 'x'
        used_ids.add(cid)
        kind = str(c.get('kind') or 'service').strip().lower()
        if kind not in COMPONENT_KINDS:
            log.warning('propose_architecture: dropping invalid component kind %r', kind)
            kind = 'service'
        raw_id = str(c.get('id') or '').strip()
        if raw_id:
            id_map.setdefault(raw_id, cid)   # first component wins ambiguous references
        comps.append({
            'id': cid,
            'name': str(c.get('name') or 'Component %d' % i),
            'responsibility': str(c.get('responsibility') or ''),
            'kind': kind,
            'requirement_ids': [str(x) for x in (c.get('requirement_ids') or [])],
        })
    ids = {c['id'] for c in comps}
    rels = []
    seen_rels = set()
    used_rel_ids = set()
    for i, r in enumerate(data.get('relationships') or [], 1):
        if not isinstance(r, dict):
            continue
        src = id_map.get(str(r.get('src') or '').strip(), str(r.get('src') or '').strip())
        dst = id_map.get(str(r.get('dst') or '').strip(), str(r.get('dst') or '').strip())
        if src not in ids or dst not in ids or src == dst:
            continue   # drop dangling/self relationships instead of failing the proposal
        kind = str(r.get('kind') or 'calls').strip().lower()
        if kind not in RELATIONSHIP_KINDS:
            log.warning('propose_architecture: normalising invalid relationship kind %r', kind)
            kind = 'calls'
        edge_key = (src, dst, kind)
        if edge_key in seen_rels:
            continue   # duplicate relationship
        seen_rels.add(edge_key)
        rid = str(r.get('id') or '').strip() or 'e%d' % i
        if rid in used_rel_ids:
            rid = 'e%d' % (len(used_rel_ids) + 1)
            while rid in used_rel_ids:
                rid += 'x'
        used_rel_ids.add(rid)
        rels.append({'id': rid, 'src': src, 'dst': dst,
                     'kind': kind, 'label': str(r.get('label') or '')})
    if not comps:
        h = heuristic()
        comps, rels = h['components'], h['relationships']
    return {'status': 'ok', 'components': comps, 'relationships': rels}


def _tokens(s: str) -> set:
    """Word tokens for fuzzy matching: splits snake/kebab/camel case and paths."""
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', s or '')
    return {t for t in re.split(r'[^A-Za-z0-9]+', s.lower()) if len(t) > 1}


def _graph_data():
    """Load the repository graph once: (nodes, edges, normalized-name index)."""
    nodes, edges = [], []
    try:
        path = config.GRAPH_PATH
        if path.is_file():
            data = json.loads(path.read_text())
            nodes = data.get('nodes') or []
            edges = data.get('edges') or []
    except Exception as exc:
        log.warning('compare_to_repository could not read graph: %s', exc)
    index = {}
    for n in nodes:
        for key in (n.get('name'), n.get('id'), n.get('qualname')):
            if key:
                index.setdefault(_norm(key), n)
    return nodes, edges, index


def _node_tokens(n) -> set:
    parts = [n.get('name'), n.get('qualname'), n.get('id'), n.get('file'), n.get('module')]
    toks = set()
    for p in parts:
        toks |= _tokens(str(p or ''))
    return toks


def _match_component(comp, nodes):
    """Best graph node for a component: exact normalised name, then token
    overlap (Jaccard), then normalised containment as a weak last resort.
    Returns (node, score, how)."""
    name = str(comp.get('name') or '')
    nn = _norm(name)
    if not nn:
        return None, 0.0, ''
    ctoks = _tokens(name)
    best, best_score = None, 0.0
    for n in nodes:
        if n.get('level') in ('module', 'file') and not ctoks:
            continue
        ntoks = _node_tokens(n)
        if not ntoks:
            continue
        inter = len(ctoks & ntoks)
        score = inter / len(ctoks | ntoks) if ctoks else 0.0
        # Exact normalised equality always wins outright.
        keys = [_norm(n.get(k)) for k in ('name', 'id', 'qualname')]
        if nn in keys:
            return n, 1.0, 'exact name match'
        if score > best_score:
            best, best_score = n, score
    if best is not None and best_score >= 0.5:
        return best, best_score, 'token overlap %.2f' % best_score
    # Weak fallback: normalised containment either way (kept for recall, but
    # reported as fuzzy so it is not mistaken for a confident match).
    for n in nodes:
        for key in ('name', 'id', 'qualname'):
            k = _norm(n.get(key))
            if k and (nn in k or k in nn):
                return n, 0.25, 'fuzzy name containment'
    return None, 0.0, ''


def _scopes(node_id, nodes):
    """node_id plus every descendant (via the parent chain / contains edges)."""
    children = {}
    for n in nodes:
        p = n.get('parent')
        if p:
            children.setdefault(p, []).append(n.get('id'))
    scope, stack = set(), [node_id]
    while stack:
        cur = stack.pop()
        if cur in scope:
            continue
        scope.add(cur)
        stack.extend(children.get(cur, ()))
    return scope


def _edge_kind_rank(e):
    return 0 if e.get('kind') == 'confirmed' else 1


def compare_to_repository(architecture, tool_context: ToolContext = None) -> dict:
    """Map each proposed component onto repository graph nodes and check each
    proposed relationship against actual repository edges.

    Returns {matched, missing, extra, relationships}. matched/missing/extra
    carry the component (or node) id, name and the evidence used; each
    relationship entry reports 'confirmed', 'possible', 'missing' or
    'unmatched' with the repository edge (or its absence) as evidence.
    """
    arch = architecture.get('architecture', architecture) if isinstance(architecture, dict) else {}
    comps = arch.get('components') or []
    rels = arch.get('relationships') or []
    nodes, edges, _index = _graph_data()

    matched, missing = [], []
    node_of = {}        # component id -> graph node id
    used_nodes = set()
    for c in comps:
        cid = str(c.get('id'))
        hit, score, how = _match_component(c, nodes)
        if hit is not None:
            nid = hit.get('id') or hit.get('name')
            matched.append({'id': cid, 'name': str(c.get('name') or ''), 'node': nid,
                            'evidence': '%s (%s) [%s]' % (nid, hit.get('file') or '?', how)})
            node_of[cid] = nid
            used_nodes.add(nid)
        else:
            missing.append({'id': cid, 'name': str(c.get('name') or ''),
                            'node': '', 'evidence': 'no graph node matches'})

    # Relationship comparison: does a real (non-'contains') repository edge
    # connect the two matched components' scopes, in the proposed direction?
    scopes = {cid: _scopes(nid, nodes) for cid, nid in node_of.items()}
    node_name = {n.get('id'): (n.get('name') or n.get('id')) for n in nodes}
    rel_results = []
    for r in rels:
        rid = str(r.get('id') or '')
        src, dst = str(r.get('src') or ''), str(r.get('dst') or '')
        kind = str(r.get('kind') or 'calls')
        entry = {'id': rid, 'src': src, 'dst': dst, 'kind': kind,
                 'status': 'missing', 'evidence': ''}
        if src not in scopes or dst not in scopes:
            entry['status'] = 'unmatched'
            entry['evidence'] = 'one or both endpoints have no repository match'
        else:
            a_scope, b_scope = scopes[src], scopes[dst]
            candidates = [e for e in edges
                          if e.get('src') in a_scope and e.get('dst') in b_scope
                          and e.get('type') != 'contains']
            if candidates:
                candidates.sort(key=_edge_kind_rank)
                e = candidates[0]
                entry['status'] = 'confirmed' if e.get('kind') == 'confirmed' else 'possible'
                entry['evidence'] = '%s -> %s (%s, %s)' % (
                    e.get('src'), e.get('dst'), e.get('type'), e.get('kind'))
            else:
                entry['evidence'] = 'no repository edge between %s and %s' % (
                    node_of.get(src), node_of.get(dst))
        rel_results.append(entry)

    extra = [{'id': n.get('id') or n.get('name'), 'name': n.get('name') or n.get('id'),
              'node': n.get('id'), 'evidence': n.get('file') or ''}
             for n in nodes
             if (n.get('id') or n.get('name')) not in used_nodes
             and n.get('level') not in ('module', 'file')]
    return {'status': 'ok', 'matched': matched, 'missing': missing,
            'extra': extra[:50], 'relationships': rel_results}


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
