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
import subprocess
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
    """Ask the model for a JSON object. Returns (data, source) where source is
    'model' or 'heuristic' — callers MUST surface this so a fallback proposal is
    never presented as AI-generated. Falls back to `fallback()` when there is
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
            return data, 'model'
    except Exception as exc:
        log.warning('architecture LLM call failed, using heuristic fallback: %s', exc)
    return fallback(), 'heuristic'


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

    data, source = _llm_json(
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
        source = 'heuristic'   # model replied with nothing usable
    return {'status': 'ok', 'source': source, 'requirements': req}


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

    data, source = _llm_json(
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
        source = 'heuristic'   # model output had no usable components
    return {'status': 'ok', 'source': source,
            'components': comps, 'relationships': rels}


def _tokens(s: str) -> set:
    """Word tokens for fuzzy matching: splits snake/kebab/camel case and paths.
    Adds a naive singular (services -> service) so plurals still match."""
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', s or '')
    out = set()
    for t in re.split(r'[^A-Za-z0-9]+', s.lower()):
        if len(t) <= 1:
            continue
        out.add(t)
        if len(t) > 3 and t.endswith('s') and not t.endswith('ss'):
            out.add(t[:-1])
    return out


def _graph_data(graph_path=None):
    """Load the repository graph once: (nodes, edges, normalized-name index).

    `graph_path` overrides config.GRAPH_PATH so a session can compare against a
    repository other than the globally active one."""
    nodes, edges = [], []
    try:
        path = Path(graph_path) if graph_path else config.GRAPH_PATH
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


_LEVEL_RANK = {'module': 0, 'file': 1, 'class': 2, 'function': 3}


def _component_tokens(comp):
    """Tokens describing a component: name plus responsibility text."""
    toks = _tokens(str(comp.get('name') or ''))
    toks |= _tokens(str(comp.get('responsibility') or ''))
    return toks


def _match_candidates(comp, nodes, limit=8):
    """Ranked repository-node candidates for a component.

    Returns [(node, score, how), ...] best-first. Scoring tiers:
      1.00  exact normalised equality with name/id/qualname
      0.90  the component name equals a module or file name/path stem
      jaccard  token overlap between component and node tokens (>= 0.34)
      0.25  normalised containment either way (weak, reported as fuzzy)
    """
    name = str(comp.get('name') or '')
    nn = _norm(name)
    if not nn:
        return []
    ctoks = _component_tokens(comp) or _tokens(name)
    scored = []
    for n in nodes:
        ntoks = _node_tokens(n)
        if not ntoks:
            continue
        inter = len(ctoks & ntoks)
        jaccard = inter / len(ctoks | ntoks) if ctoks else 0.0
        keys = [_norm(n.get(k)) for k in ('name', 'id', 'qualname')]
        if nn in keys:
            scored.append((n, 1.0, 'exact name match'))
            continue
        # A component named like a module/file ("auth", "account service")
        # should match that container, not an arbitrary symbol inside it.
        file_stem = _norm(str(n.get('file') or '').rsplit('/', 1)[-1].rsplit('.', 1)[0])
        if n.get('level') in ('module', 'file') and nn and nn == file_stem:
            scored.append((n, 0.9, 'module/file name match'))
            continue
        if jaccard >= 0.5:
            scored.append((n, jaccard, 'token overlap %.2f' % jaccard))
        elif jaccard >= 0.34:
            scored.append((n, jaccard * 0.8, 'weak token overlap %.2f' % jaccard))
    # Fuzzy containment as a last resort, below every scored candidate.
    fuzzy = []
    for n in nodes:
        for key in ('name', 'id', 'qualname', 'file'):
            k = _norm(n.get(key))
            if k and len(k) >= 4 and (nn in k or k in nn):
                fuzzy.append((n, 0.25, 'fuzzy name containment'))
                break
    scored.extend(fuzzy)
    # Best score first; on ties prefer coarser nodes (module > file > class >
    # function) so a component lands on the architectural unit, not a symbol.
    scored.sort(key=lambda t: (-t[1], _LEVEL_RANK.get(t[0].get('level'), 9),
                               str(t[0].get('id'))))
    # dedupe by node id, keep best rank
    seen, out = set(), []
    for n, s, how in scored:
        nid = n.get('id')
        if nid in seen:
            continue
        seen.add(nid)
        out.append((n, s, how))
        if len(out) >= limit:
            break
    return out


def _assign_matches(comps, nodes):
    """Assign each component at most one repository node and each node at most
    one component (global greedy by score). Returns (node_of, matched_info,
    missing_info) where node_of maps component id -> node id."""
    cand_lists = []
    flat = []
    for i, c in enumerate(comps):
        cands = _match_candidates(c, nodes)
        cand_lists.append(cands)
        for rank, (n, s, how) in enumerate(cands):
            flat.append((-s, _LEVEL_RANK.get(n.get('level'), 9), str(n.get('id')), i, rank))
    flat.sort()
    comp_of_node, node_of, used_cands = {}, {}, {}
    for neg_s, _lr, _nid, i, rank in flat:
        cid = str(comps[i].get('id'))
        if cid in node_of:
            continue
        node = cand_lists[i][rank][0]
        nid = node.get('id') or node.get('name')
        if nid in comp_of_node:
            continue                      # node already claimed by a better match
        node_of[cid] = nid
        comp_of_node[nid] = cid
        used_cands[cid] = cand_lists[i][rank]
    matched, missing = [], []
    for i, c in enumerate(comps):
        cid = str(c.get('id'))
        if cid in node_of:
            n, s, how = used_cands[cid]
            nid = node_of[cid]
            matched.append({'id': cid, 'name': str(c.get('name') or ''), 'node': nid,
                            'score': round(s, 3),
                            'confidence': ('high' if s >= 0.9 else
                                           'medium' if s >= 0.5 else 'low'),
                            'evidence': '%s (%s) [%s]' % (nid, n.get('file') or '?', how)})
        else:
            cands = cand_lists[i]
            best = cands[0] if cands else None
            why = ('best candidate %s already claimed by another component'
                   % (best[0].get('id') if best else 'none'))
            missing.append({'id': cid, 'name': str(c.get('name') or ''),
                            'node': '', 'score': 0.0,
                            'evidence': 'no unclaimed graph node matches (%s)' % why})
    return node_of, matched, missing


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


# Proposed relationship kinds -> repository edge types that can confirm them.
# The graph records 'calls'/'may_call' for call edges and 'imports' for
# module dependencies; there is no separate reads/publishes edge type, so
# those proposals can only be corroborated by the closest available evidence.
EDGE_TYPES_FOR_KIND = {
    'calls': {'calls', 'may_call'},
    'reads': {'imports', 'reads'},
    'publishes': {'publishes', 'exports', 'imports'},
}


def compare_to_repository(architecture, tool_context: ToolContext = None,
                          graph_path=None) -> dict:
    """Map each proposed component onto repository graph nodes and check each
    proposed relationship against actual repository edges.

    Components are assigned to graph nodes globally (one node per component,
    one component per node) so two proposed components cannot silently claim
    the same repository unit. Relationships are checked for BOTH connectivity
    and semantic type: an 'imports' edge does not confirm a proposed 'calls'
    relationship — it is reported as 'possible' with the mismatch in evidence.

    Returns {matched, missing, extra, relationships}. matched/missing/extra
    carry the component (or node) id, name and the evidence used; each
    relationship entry reports 'confirmed', 'possible', 'missing' or
    'unmatched' with the repository edge (or its absence) as evidence.
    """
    arch = architecture.get('architecture', architecture) if isinstance(architecture, dict) else {}
    comps = arch.get('components') or []
    rels = arch.get('relationships') or []
    nodes, edges, _index = _graph_data(graph_path)

    node_of, matched, missing = _assign_matches(comps, nodes)
    used_nodes = set(node_of.values())

    # Relationship comparison: does a real (non-'contains') repository edge
    # connect the two matched components' scopes, in the proposed direction,
    # and does its type match the proposed relationship kind?
    scopes = {cid: _scopes(nid, nodes) for cid, nid in node_of.items()}
    rel_results = []
    for r in rels:
        rid = str(r.get('id') or '')
        src, dst = str(r.get('src') or ''), str(r.get('dst') or '')
        kind = str(r.get('kind') or 'calls')
        wanted = EDGE_TYPES_FOR_KIND.get(kind, {'calls', 'may_call'})
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
            semantic = [e for e in candidates if e.get('type') in wanted]
            if semantic:
                semantic.sort(key=_edge_kind_rank)
                e = semantic[0]
                entry['status'] = 'confirmed' if e.get('kind') == 'confirmed' else 'possible'
                entry['evidence'] = '%s -> %s (%s, %s)' % (
                    e.get('src'), e.get('dst'), e.get('type'), e.get('kind'))
            elif candidates:
                # Connectivity exists but the edge type does not match the
                # proposed relationship semantics.
                candidates.sort(key=_edge_kind_rank)
                e = candidates[0]
                entry['status'] = 'possible'
                entry['evidence'] = ('%s -> %s (%s, %s); type does not match '
                                     'proposed kind %r' % (
                                         e.get('src'), e.get('dst'),
                                         e.get('type'), e.get('kind'), kind))
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


def generate_implementation_plan(architecture, tool_context: ToolContext = None,
                                 graph_path=None) -> dict:
    """Turn an approved architecture into a dependency-ordered task list.

    Tasks are ordered so a component's task depends on the tasks of the
    components it calls/reads. Each task is grounded in the repository graph:
    it names the files to change, the key symbols to modify, and concrete
    acceptance criteria. `graph_path` overrides config.GRAPH_PATH.
    Returns {tasks: [...]} with depends_on, component_id, acceptance,
    files, symbols and owner on every task.
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

    # Ground every task in the repository: which files implement the component
    # and which symbols are the likely edit points. Loaded once for all tasks.
    grounding = _repo_grounding(comps, graph_path=graph_path)

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
        g = grounding.get(cid) or {'files': [], 'symbols': [], 'match': 'unmatched'}
        criteria = []
        if comp.get('responsibility'):
            criteria.append('Responsibility: ' + str(comp['responsibility']))
        if g['files']:
            criteria.append('Change is confined to: ' + ', '.join(g['files']))
        if g['symbols']:
            criteria.append('Primary symbols: ' + ', '.join(
                s['name'] for s in g['symbols']))
        if g['match'] == 'unmatched':
            criteria.append('No repository component matched; identify the '
                            'target files during implementation and record them.')
        tasks.append({'id': tid, 'title': 'Implement ' + comp.get('name', cid),
                      'status': 'pending', 'component_id': cid,
                      'depends_on': [task_of[d] for d in depends],
                      'acceptance': comp.get('responsibility') or '',
                      'acceptance_criteria': criteria,
                      'files': g['files'],
                      'symbols': g['symbols'],
                      'repo_match': g['match'],
                      'owner': 'developer'})

    return {'status': 'ok', 'tasks': tasks, 'circular': cyclic}


def _repo_grounding(comps, graph_path=None):
    """Map each component to concrete repository files and key symbols.

    Returns {component_id: {'files': [relpaths], 'symbols': [{id,name,file}],
    'match': 'repository'|'unmatched'}}. Symbols are ranked by confirmed+possible
    incoming call edges so the most depended-on functions surface first.
    """
    out = {str(c.get('id')): {'files': [], 'symbols': [], 'match': 'unmatched'}
           for c in comps}
    try:
        nodes, edges, _index = _graph_data(graph_path)
    except Exception:
        return out
    if not nodes:
        return out

    # Reuse the comparison matcher so grounding and comparison agree on which
    # repository unit a component refers to.
    node_of, _matched, _missing = _assign_matches(comps, nodes)
    node_by_id = {n.get('id'): n for n in nodes}

    # Incoming-edge counts per symbol (confirmed calls weigh more than may_call).
    in_degree = {}
    for e in edges:
        if e.get('type') in ('calls', 'may_call'):
            w = 2 if e.get('kind') == 'confirmed' else 1
            in_degree[e.get('dst')] = in_degree.get(e.get('dst'), 0) + w

    for c in comps:
        cid = str(c.get('id'))
        nid = node_of.get(cid)
        if not nid:
            continue
        node = node_by_id.get(nid)
        if node is None:
            continue
        # Collect the file nodes inside this component's scope. If the match
        # landed on a symbol, walk up to its file first.
        scope = _scopes(nid, nodes)
        file_nodes = [n for n in nodes
                      if n.get('id') in scope and n.get('level') == 'file']
        if not file_nodes:
            cur = node
            while cur is not None and cur.get('level') != 'file':
                cur = node_by_id.get(cur.get('parent'))
            if cur is not None:
                file_nodes = [cur]
                scope = _scopes(cur.get('id'), nodes) | {nid}
        files = []
        for fn in file_nodes:
            f = fn.get('file')
            if f and f not in files:
                files.append(f)
        files = files[:5]
        # Symbols in those files, ranked by how many callers depend on them.
        file_ids = {fn.get('id') for fn in file_nodes}
        syms = [n for n in nodes
                if n.get('id') in scope and n.get('level') in ('function', 'class')
                and n.get('parent') in file_ids]
        syms.sort(key=lambda n: (-in_degree.get(n.get('id'), 0), str(n.get('id'))))
        symbols = [{'id': n.get('id'), 'name': n.get('name') or n.get('qualname') or '',
                    'file': n.get('file') or ''} for n in syms[:5]]
        out[cid] = {'files': files, 'symbols': symbols, 'match': 'repository'}
    return out


# ---------------------------------------------------------------------------
# Task-completion evidence verification

_HEX_RE = re.compile(r'\b[0-9a-f]{7,40}\b')
_BRANCH_RE = re.compile(r'\b[a-zA-Z][\w.-]*(?:/[\w.:-]+)+\b')
_PYTEST_ID_RE = re.compile(r'([\w./-]+\.py)::([\w.:\[\]-]+)')
_NODE_ID_RE = re.compile(r'\b((?:file::)?[\w./-]+(?:::[\w.$~\[\]-]+)+)\b')
_SKIP_BRANCHES = {'and/or', 'either/or'}


def _git(root, *args):
    try:
        p = subprocess.run(['git', '-C', str(root), *args],
                           capture_output=True, text=True, timeout=10)
        return p.returncode == 0, (p.stdout or '').strip()
    except Exception:
        return False, ''


def _load_node_ids(graph_path=None):
    try:
        path = Path(graph_path) if graph_path else config.GRAPH_PATH
        if path.is_file():
            data = json.loads(path.read_text())
            return {str(n.get('id')) for n in (data.get('nodes') or [])}
    except Exception as exc:
        log.warning('verify_task_evidence could not read graph: %s', exc)
    return set()


def verify_task_evidence(evidence: str, repo_root=None, graph_path=None) -> dict:
    """Independently check the checkable claims inside a task-completion
    evidence string against the repository and its graph.

    Recognised claims:
      - git commit SHAs (7-40 hex chars)        -> must resolve to a commit
      - branch names containing '/'             -> must be a local branch
      - pytest node ids  path.py::test_name     -> file must exist and contain
                                                 the test name
      - graph node ids  file::x.py::qual.name   -> must exist in the graph

    Claims that cannot be checked ("manual review", "N passed") are reported
    as 'unknown', not failures. Verdict:
      'failed'      at least one checkable claim contradicts the repository
      'verified'    at least one claim verified and none failed
      'unverified'  nothing checkable was found
    """
    text = (evidence or '').strip()
    checks = []
    if not text:
        return {'status': 'ok', 'verdict': 'unverified', 'checks': []}

    root = Path(repo_root) if repo_root else Path(config.REPO_ROOT)
    is_git = (root / '.git').exists()

    # --- commit SHAs -------------------------------------------------------
    for tok in sorted(set(_HEX_RE.findall(text))):
        if len(tok) < 7:
            continue
        if is_git:
            ok, _ = _git(root, 'rev-parse', '--verify', '--quiet', tok + '^{commit}')
            checks.append({'claim': tok, 'kind': 'commit',
                           'status': 'verified' if ok else 'failed',
                           'detail': 'commit exists' if ok else 'not a commit in repo'})
        else:
            checks.append({'claim': tok, 'kind': 'commit', 'status': 'unknown',
                           'detail': 'repository is not a git checkout'})

    # --- branch names ------------------------------------------------------
    # Only well-known branch prefixes are treated as claims; arbitrary
    # "a/b" text (e.g. "docs/README") is ignored rather than failed.
    _BRANCH_PREFIXES = ('jarvis/', 'feature/', 'fix/', 'chore/', 'devin/')
    for tok in sorted(set(_BRANCH_RE.findall(text))):
        if tok.lower() in _SKIP_BRANCHES or '..' in tok:
            continue
        if not tok.lower().startswith(_BRANCH_PREFIXES):
            continue
        if is_git:
            ok, _ = _git(root, 'rev-parse', '--verify', '--quiet',
                         'refs/heads/' + tok)
            checks.append({'claim': tok, 'kind': 'branch',
                           'status': 'verified' if ok else 'failed',
                           'detail': 'local branch exists' if ok else 'no such branch'})
        else:
            checks.append({'claim': tok, 'kind': 'branch', 'status': 'unknown',
                           'detail': 'repository is not a git checkout'})

    # --- pytest node ids ---------------------------------------------------
    for path, name in sorted(set(_PYTEST_ID_RE.findall(text))):
        target = (root / path)
        try:
            target = target.resolve()
            target.relative_to(root.resolve())
        except Exception:
            checks.append({'claim': path + '::' + name, 'kind': 'pytest',
                           'status': 'failed', 'detail': 'path escapes repository'})
            continue
        if not target.is_file():
            checks.append({'claim': path + '::' + name, 'kind': 'pytest',
                           'status': 'failed', 'detail': 'test file not found'})
            continue
        try:
            body = target.read_text(errors='replace')
        except OSError:
            body = ''
        leaf = name.split('::')[-1].split('[')[0]
        ok = leaf in body
        checks.append({'claim': path + '::' + name, 'kind': 'pytest',
                       'status': 'verified' if ok else 'failed',
                       'detail': 'test name found in file' if ok
                                 else 'test name not found in file'})

    # --- graph node ids ----------------------------------------------------
    node_ids = _load_node_ids(graph_path)
    if node_ids:
        for tok in sorted(set(_NODE_ID_RE.findall(text))):
            # Strip a trailing sentence period before checking.
            cand = tok.rstrip('.')
            if cand in node_ids:
                checks.append({'claim': cand, 'kind': 'graph_node',
                               'status': 'verified',
                               'detail': 'node exists in graph'})
            elif cand.count('::') >= 1:
                checks.append({'claim': cand, 'kind': 'graph_node',
                               'status': 'unknown',
                               'detail': 'not a graph node id'})

    if any(c['status'] == 'failed' for c in checks):
        verdict = 'failed'
    elif any(c['status'] == 'verified' for c in checks):
        verdict = 'verified'
    else:
        verdict = 'unverified'
    return {'status': 'ok', 'verdict': verdict, 'checks': checks}


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
