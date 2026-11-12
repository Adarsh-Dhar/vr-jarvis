"""
Architecture design tools.

Structured idea -> requirements -> proposed architecture -> repository
comparison -> implementation plan. Model output only ever *proposes*: the
session state keeps status='draft' until a human approves through the API,
and an approved architecture reverts to draft on any edit.
"""

import json
import logging
import os
from collections import Counter
import math
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from google.adk.tools import ToolContext

from .. import config

log = logging.getLogger(__name__)

REQUIREMENT_KEYS = ('goals', 'functional', 'non_functional', 'constraints', 'assumptions', 'open_questions')
ARCH_VERSION = 3
DESIGN_DIR = config.ROOT / 'data' / 'design'

# Canonical vocabularies; model output outside these is normalised, not trusted.
COMPONENT_KINDS = ('service', 'library', 'ui', 'data', 'external')
RELATIONSHIP_KINDS = ('calls', 'reads', 'publishes')


def _put_design(tool_context, **values):
    """Write tool results into the SAME session keys the /design endpoints use
    (design_requirements, design, design_compare, implementation_plan) and
    persist them, so the root agent and the VR UI share one design state.
    No-op when called without a tool context (the endpoints call the tools
    directly and persist on their own)."""
    state = getattr(tool_context, 'state', None)
    if state is None:
        return
    for key, value in values.items():
        state[key] = value
    sid = state.get('session_id')
    if sid:
        save_design(sid, {'requirements': state.get('design_requirements'),
                          'architecture': state.get('design'),
                          'compare': state.get('design_compare'),
                          'plan': state.get('implementation_plan')})


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
    _put_design(tool_context, design_requirements=req)
    return {'status': 'ok', 'source': source, 'requirements': req}


def propose_architecture(requirements: Union[Dict[str, Any], str], tool_context: ToolContext = None) -> dict:
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
    arch = _blank_architecture()
    arch['components'] = comps
    arch['relationships'] = rels
    arch['open_questions'] = list(req.get('open_questions') or [])
    arch['provenance'] = source
    arch['revision'] = 1
    # A new proposal invalidates any earlier comparison and plan.
    _put_design(tool_context, design_requirements=req, design=arch,
                design_compare={}, implementation_plan={})
    return {'status': 'ok', 'source': source,
            'components': comps, 'relationships': rels}


def _stem_variants(t):
    """Cheap suffix variants so 'handler'/'handling'/'handled' can meet
    'handle'. Emits at most a few extra forms per token; approximate by
    design — exact and module/file matches still outrank everything here."""
    out = set()
    if len(t) > 5 and t.endswith('ing'):
        stem = t[:-3]
        out.update(x for x in (stem, stem + 'e') if len(x) > 2)
    if len(t) > 4 and t.endswith('ed'):
        stem = t[:-2]
        out.update(x for x in (stem, stem + 'e') if len(x) > 2)
    if len(t) > 5 and t.endswith('ies'):
        out.add(t[:-3] + 'y')
    if len(t) > 5 and t.endswith('er'):
        out.add(t[:-2] + 'e')          # handler -> handle, manager -> manage
    if len(t) > 6 and t.endswith('ation'):
        out.add(t[:-5] + 'ate')       # authentication -> authenticate
    if len(t) > 4 and t.endswith('ly'):
        out.add(t[:-2])
    return out


def _tokens(s: str) -> set:
    """Word tokens for fuzzy matching: splits snake/kebab/camel case and paths.
    Adds a naive singular (services -> service), light suffix stems, and
    common morphological variants so plurals/inflections still match."""
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', s or '')
    out = set()
    for t in re.split(r'[^A-Za-z0-9]+', s.lower()):
        if len(t) <= 1:
            continue
        out.add(t)
        if len(t) > 3 and t.endswith('s') and not t.endswith('ss'):
            out.add(t[:-1])
        out |= _stem_variants(t)
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


def _component_token_weights(comp):
    """token -> weight. Name tokens count double responsibility tokens so a
    component called 'Auth' is not diluted by a long responsibility paragraph."""
    w = {}
    for t in _tokens(str(comp.get('name') or '')):
        w[t] = max(w.get(t, 0.0), 2.0)
    for t in _tokens(str(comp.get('responsibility') or '')):
        w[t] = max(w.get(t, 0.0), 1.0)
    return w


def _node_token_weights(n):
    """token -> weight. Declared names/qualnames count double path and module
    tokens, which are shared by every symbol in the same file."""
    w = {}
    for key, mult in (('name', 2.0), ('qualname', 2.0),
                      ('id', 1.0), ('file', 1.0), ('module', 1.0)):
        for t in _tokens(str(n.get(key) or '')):
            w[t] = max(w.get(t, 0.0), mult)
    return w


def _token_idf(nodes):
    """Inverse document frequency over node token sets. Ubiquitous tokens
    ('service', 'utils', 'test') carry almost no signal; rare tokens dominate
    both the jaccard and the coverage score."""
    df = {}
    for n in nodes:
        for t in _node_token_weights(n):
            df[t] = df.get(t, 0) + 1
    n_nodes = max(1, len(nodes))
    return {t: math.log((n_nodes + 1.0) / (c + 0.5)) for t, c in df.items()}


_LEVEL_RANK = {'module': 0, 'file': 1, 'class': 2, 'function': 3}


def _match_candidates(comp, entries, idf, limit=8):
    """Ranked repository-node candidates for a component.

    `entries` is [(node, weighted_tokens, token_weight_total), ...] built once
    per comparison; `idf` maps token -> inverse document frequency so common
    words stop dominating the overlap score.

    Returns [(node, score, how), ...] best-first. Scoring tiers:
      1.00  exact normalised equality with name/id/qualname
      0.90  the component name equals a module or file name/path stem
      token  weighted jaccard + coverage over idf-scaled token weights
      0.25  normalised containment either way (weak, reported as fuzzy)
    """
    name = str(comp.get('name') or '')
    nn = _norm(name)
    if not nn:
        return []
    cw = _component_token_weights(comp) or {t: 1.0 for t in _tokens(name)}
    cw = {t: m * idf.get(t, 1.0) for t, m in cw.items()}
    ctot = sum(cw.values())
    scored = []
    for n, nw, ntot in entries:
        if not nw or not ctot:
            continue
        inter = sum(min(cw[t], nw[t]) for t in cw.keys() & nw.keys())
        union = ctot + ntot - inter
        jaccard = inter / union if union else 0.0
        coverage = inter / ctot
        # Weighted jaccard penalises nodes with many unrelated tokens; the
        # coverage term rewards a node that explains most of the component's
        # weighted tokens even when the node itself is broad. The bonus is
        # capped below the 'medium confidence' line so it can propose but
        # never silently auto-assign on token evidence alone.
        tok = jaccard
        if coverage >= 0.6:
            tok = max(tok, min(0.49, 0.55 * coverage))
        # A component named like a module/file ("auth", "account service")
        # should match that container, not an arbitrary symbol inside it.
        keys = [_norm(n.get(k)) for k in ('name', 'id', 'qualname')]
        if nn in keys:
            scored.append((n, 1.0, 'exact name match'))
            continue
        file_stem = _norm(str(n.get('file') or '').rsplit('/', 1)[-1].rsplit('.', 1)[0])
        if n.get('level') in ('module', 'file') and nn and nn == file_stem:
            scored.append((n, 0.9, 'module/file name match'))
            continue
        if tok >= 0.5:
            scored.append((n, tok, 'token overlap %.2f' % tok))
        elif tok >= 0.34:
            scored.append((n, tok * 0.8, 'weak token overlap %.2f' % tok))
    # Fuzzy containment as a last resort, below every scored candidate.
    fuzzy = []
    for n, _nw, _ntot in entries:
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


def _assign_matches(comps, nodes, override_matches=None):
    """Assign each component at most one repository node and each node at most
    one component (global greedy by score). Returns (node_of, matched_info,
    missing_info, ambiguous_info).

    A component whose top two candidates score within AMBIGUITY_MARGIN is NOT
    auto-assigned: it is reported in `ambiguous` for the developer to resolve
    (compare_to_repository accepts override_matches for that)."""
    AMBIGUITY_MARGIN = 0.12
    override_matches = override_matches or {}
    # Precompute idf-scaled token weights once for the whole comparison.
    idf = _token_idf(nodes)
    entries = []
    for n in nodes:
        nw = {t: m * idf.get(t, 1.0) for t, m in _node_token_weights(n).items()}
        entries.append((n, nw, sum(nw.values())))
    cand_lists = []
    flat = []
    ambiguous_ids = set()
    for i, c in enumerate(comps):
        cid = str(c.get('id'))
        cands = _match_candidates(c, entries, idf)
        cand_lists.append(cands)
        # Explicit developer override wins over scoring entirely.
        if cid in override_matches:
            continue
        if len(cands) >= 2 and cands[0][1] - cands[1][1] < AMBIGUITY_MARGIN \
                and cands[0][1] < 1.0:
            ambiguous_ids.add(cid)
            continue
        for rank, (n, s, how) in enumerate(cands):
            flat.append((-s, _LEVEL_RANK.get(n.get('level'), 9), str(n.get('id')), i, rank))
    flat.sort()
    comp_of_node, node_of, used_cands = {}, {}, {}
    for neg_s, _lr, _nid, i, rank in flat:
        cid = str(comps[i].get('id'))
        if cid in node_of or cid in ambiguous_ids:
            continue
        node = cand_lists[i][rank][0]
        nid = node.get('id') or node.get('name')
        if nid in comp_of_node:
            continue                      # node already claimed by a better match
        node_of[cid] = nid
        comp_of_node[nid] = cid
        used_cands[cid] = cand_lists[i][rank]
    # Apply explicit overrides after greedy assignment.
    node_by_id = {n.get('id'): n for n in nodes}
    for cid, nid in override_matches.items():
        cid = str(cid)
        if cid not in {str(c.get('id')) for c in comps}:
            continue
        if nid not in node_by_id:
            continue
        old = node_of.get(cid)
        if old and old != nid:
            comp_of_node.pop(old, None)
        for other, assigned in list(node_of.items()):
            if other != cid and assigned == nid:
                del node_of[other]
                comp_of_node.pop(nid, None)
        node_of[cid] = nid
        comp_of_node[nid] = cid
        n = node_by_id[nid]
        used_cands[cid] = (n, 1.0, 'developer override')
    matched, missing, ambiguous = [], [], []
    for i, c in enumerate(comps):
        cid = str(c.get('id'))
        cands = [{'node': n.get('id') or n.get('name'), 'file': n.get('file') or '', 'score': round(s, 3)}
                 for n, s, _how in cand_lists[i][:5]]
        if cid in ambiguous_ids and cid not in node_of:
            ambiguous.append({'id': cid, 'name': str(c.get('name') or ''),
                              'node': '', 'score': 0.0,
                              'confidence': 'low', 'ambiguous': True, 'match': 'ambiguous',
                              'candidates': cands,
                              'evidence': 'top candidates are too close to auto-assign; '
                                          'resolve with override_matches'})
        elif cid in node_of:
            n, s, how = used_cands[cid]
            nid = node_of[cid]
            matched.append({'id': cid, 'name': str(c.get('name') or ''), 'node': nid,
                            'score': round(s, 3),
                            'confidence': ('high' if s >= 0.9 else
                                           'medium' if s >= 0.5 else 'low'),
                            'ambiguous': False, 'match': 'repository',
                            'candidates': cands,
                            'evidence': '%s (%s) [%s]' % (nid, n.get('file') or '?', how)})
        else:
            best = cand_lists[i][0] if cand_lists[i] else None
            why = ('best candidate %s already claimed by another component'
                   % (best[0].get('id') if best else 'none'))
            missing.append({'id': cid, 'name': str(c.get('name') or ''),
                            'node': '', 'score': 0.0, 'confidence': 'none',
                            'ambiguous': False, 'match': 'unmatched', 'candidates': cands,
                            'evidence': 'no unclaimed graph node matches (%s)' % why})
    return node_of, matched, missing, ambiguous


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


def compare_to_repository(architecture: Union[Dict[str, Any], str], tool_context: ToolContext = None,
                          graph_path: Optional[str] = None, repo: Optional[str] = None,
                          override_matches: Optional[Union[Dict[str, Any], str]] = None) -> dict:
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

    node_of, matched, missing, ambiguous = _assign_matches(comps, nodes, override_matches)
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
            forward = [e for e in edges
                       if e.get('src') in a_scope and e.get('dst') in b_scope
                       and e.get('type') != 'contains']
            reverse = [e for e in edges
                       if e.get('src') in b_scope and e.get('dst') in a_scope
                       and e.get('type') != 'contains']
            candidates = forward
            if not candidates and reverse:
                # Connectivity exists but in the opposite direction.
                entry['status'] = 'wrong_direction'
                reverse.sort(key=_edge_kind_rank)
                e = reverse[0]
                entry['evidence'] = ('%s -> %s (%s, %s); direction is reversed '
                                     'relative to the proposal' % (
                                         e.get('src'), e.get('dst'),
                                         e.get('type'), e.get('kind')))
                rel_results.append(entry)
                continue
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
                entry['status'] = 'wrong_type'
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
    result = {'status': 'ok', 'matched': matched, 'missing': missing,
              'ambiguous': ambiguous, 'extra': extra[:50], 'relationships': rel_results,
              'design_revision': arch.get('revision'), 'repo': repo}
    _put_design(tool_context, design_compare=result)
    return result


_SOURCE_SUFFIXES = ('.py', '.ts', '.tsx', '.js', '.jsx', '.go', '.rs', '.java', '.cs')
_LAYOUT_SKIP = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build', 'tests', 'test'}


def _source_layout(root):
    suffixes, dirs = Counter(), {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _LAYOUT_SKIP and not d.startswith('.')]
        for fn in filenames:
            ext = os.path.splitext(fn)[1]
            if ext in _SOURCE_SUFFIXES and not fn.startswith('test_') and '.test.' not in fn and '.spec.' not in fn:
                suffixes[ext] += 1
                dirs.setdefault(ext, Counter())[os.path.relpath(dirpath, root)] += 1
    if not suffixes:
        return '.py', ''
    ext = suffixes.most_common(1)[0][0]
    top = dirs[ext].most_common(1)[0][0]
    return ext, ('' if top == '.' else top.replace(os.sep, '/') + '/')


def _suggest_new_files(comp, grounding, layout, root, taken):
    if grounding.get('match') != 'unmatched':
        return []
    slug = re.sub(r'[^a-z0-9]+', '_', str(comp.get('name') or comp.get('id') or '').lower()).strip('_')
    if not slug:
        return []
    ext, prefix = layout
    path, n = prefix + slug + ext, 2
    while path in taken or os.path.exists(os.path.join(root, path)):
        path = '%s%s_%d%s' % (prefix, slug, n, ext)
        n += 1
    taken.add(path)
    return [path]


def generate_implementation_plan(architecture: Union[Dict[str, Any], str], tool_context: ToolContext = None,
                                 graph_path: Optional[str] = None) -> dict:
    """Turn an approved architecture into a dependency-ordered task list.

    Tasks are ordered so a component's task depends on the tasks of the
    components it calls/reads. Each task is grounded in the repository graph:
    it names the files to change, the key symbols to modify, and concrete
    acceptance criteria. `graph_path` overrides config.GRAPH_PATH.
    Returns {tasks: [...]} with depends_on, component_id, acceptance,
    files, symbols and owner on every task.
    """
    shared = (getattr(tool_context, 'state', None) or {}).get('design')
    if shared is not None and shared.get('status') != 'approved':
        return {'status': 'error', 'tasks': [], 'circular': [],
                'error': 'Architecture must be approved by the developer before a plan is generated.'}
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

    # Ordered cycle paths (e.g. ['c3','c5','c3']) so the UI can show the actual
    # loop instead of a bare list of component ids. Recomputed on every
    # generation, so a fixed architecture never carries stale cycle info.
    cycle_paths = _cycle_paths(deps, cyclic_set)

    # Ground every task in the repository: which files implement the component
    # and which symbols are the likely edit points. Loaded once for all tasks.
    grounding = _repo_grounding(comps, graph_path=graph_path)
    root = str(config.REPO_ROOT)
    layout = _source_layout(root)
    taken = set()

    def _subtasks(cid, comp, g):
        """Split a component into several tasks when its responsibility lists
        several actions or it matches several files."""
        actions = [s.strip() for s in re.split(r'[;\n]|\.\s+',
                    str(comp.get('responsibility') or '')) if s.strip()]
        files = list(g['files'])
        # Split when the responsibility lists several actions OR grounding
        # found several files. (The old formula ANDed the two signals through
        # a zero, so file-driven splits could never trigger.)
        signals = []
        if len(actions) > 1:
            signals.append(len(actions))
        if len(files) > 2:
            signals.append((len(files) + 1) // 2)
        n = max(1, min(3, max(signals) if signals else 1))
        if n <= 1:
            return [(comp.get('name', cid), comp.get('responsibility') or '', files, g['symbols'])]
        out = []
        for i in range(n):
            resp = actions[i] if i < len(actions) else (actions[-1] if actions else '')
            chunk = files[i::n] if files else []
            out.append(('Implement %s (%d/%d)' % (comp.get('name', cid), i + 1, n),
                        resp, chunk, g['symbols']))
        return out

    task_of = {}
    tasks = []
    seq = 0
    for cid in order:
        comp = next((c for c in comps if c['id'] == cid), None)
        if comp is None:
            continue
        g = grounding.get(cid) or {'files': [], 'symbols': [], 'match': 'unmatched'}
        unmatched = g['match'] == 'unmatched'
        comp_new_files = _suggest_new_files(comp, g, layout, root, taken)
        # Dependencies resolve to the LAST task of each dependency component
        # (a component is only "done" when its final subtask is). Computed once:
        # every dependency is already scheduled because `order` is topological.
        dep_tasks = [task_of[d] for d in sorted(deps.get(cid, ()))
                     if d in task_of and not (cid in cyclic_set and d in cyclic_set)]
        prev_tid = None
        for title, resp, files, symbols in _subtasks(cid, comp, g):
            seq += 1
            tid = 't%d' % seq
            task_of[cid] = tid   # last subtask owns dependency edges
            # First subtask waits on the dependency components' final tasks;
            # later subtasks chain off the previous subtask so split work is
            # ordered instead of leaving intra-component dependencies implicit.
            depends_on = list(dep_tasks) if prev_tid is None else [prev_tid]
            first = prev_tid is None
            prev_tid = tid
            criteria = []
            if resp:
                criteria.append('Responsibility: ' + str(resp))
            if files:
                criteria.append('Change is confined to: ' + ', '.join(files))
            if symbols:
                criteria.append('Primary symbols: ' + ', '.join(
                    s['name'] for s in symbols))
            if first and comp_new_files:
                criteria.append('Creates new file(s): ' + ', '.join(comp_new_files))
            if comp.get('requirement_ids'):
                state = getattr(tool_context, 'state', None) or {}
                reqs = state.get('design_requirements') or {}
                req_texts = []
                if isinstance(reqs, dict):
                    for key in REQUIREMENT_KEYS:
                        vals = reqs.get(key) or []
                        req_texts.extend(str(v) for v in (vals if isinstance(vals, list) else [vals]) if v)
                req_by_id = {'r%d' % i: text for i, text in enumerate(req_texts, 1)}
                for rid in comp.get('requirement_ids') or []:
                    rid = str(rid)
                    if rid in req_by_id:
                        criteria.append('Requirement: ' + req_by_id[rid])
                    elif isinstance(reqs, dict) and isinstance(reqs.get(rid), list):
                        for text in reqs[rid]:
                            criteria.append('Requirement: ' + str(text))
            if unmatched:
                criteria.append('No repository component matched; identify the '
                                'target files during investigation and record them.')
            t = {'id': tid,
                 'title': ('Investigate ' if unmatched else 'Implement ') + title,
                 'status': 'pending', 'component_id': cid,
                 'depends_on': depends_on,
                 'description': str(comp.get('responsibility') or ''),
                 'acceptance': resp,
                 'acceptance_criteria': criteria,
                 'suggested_files': files,
                 'files': files,               # alias kept for older clients
                 'confirmed_targets': [],      # filled by the coding agent
                 'rejected_targets': [],
                 'symbols': symbols,
                 'repo_match': g['match'],
                 'needs_investigation': unmatched,
                 'modifies_existing': g['match'] == 'repository',
                 'new_files': comp_new_files if first else [],
                 'design_revision': arch.get('revision'),
                 'cycle_accepted': False,
                 'cycle_rationale': '',
                 'owner': 'developer'}
            tasks.append(t)

    result = {'status': 'ok', 'tasks': tasks, 'circular': cyclic,
              'cycle_paths': cycle_paths}
    if shared is not None:
        _put_design(tool_context, implementation_plan={
            'architecture_version': shared.get('version'),
            'architecture_revision': shared.get('revision'),
            'repo': config.REPO_ROOT.name, 'status': 'active',
            'tasks': tasks, 'circular': cyclic, 'cycle_paths': cycle_paths})
    return result


def _cycle_paths(deps, cyclic_set):
    """Find one concrete dependency cycle per cyclic component, as an ordered
    path of component ids ending where it started (['c3','c5','c3'])."""
    paths = []
    seen_cycles = set()
    for start in sorted(cyclic_set):
        # DFS from start following dependency edges inside the cycle set.
        stack = [(start, [start])]
        found = None
        while stack and found is None:
            node, path = stack.pop()
            for nxt in sorted(deps.get(node, ())):
                if nxt not in cyclic_set:
                    continue
                if nxt == start and len(path) > 1:
                    found = path + [start]
                    break
                if nxt not in path:
                    stack.append((nxt, path + [nxt]))
            if found:
                break
        if found:
            key = tuple(found)
            if key not in seen_cycles:
                seen_cycles.add(key)
                paths.append(found)
    return paths


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
    node_of, _matched, _missing, _ambiguous = _assign_matches(comps, nodes)
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


def verify_task_evidence(evidence: str, repo_root: Optional[str] = None, graph_path: Optional[str] = None) -> dict:
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


def save_design(session_id: str, payload: Dict[str, Any]) -> bool:
    """Persist design state; returns False on failure so callers can warn."""
    try:
        DESIGN_DIR.mkdir(parents=True, exist_ok=True)
        _design_path(session_id).write_text(json.dumps(payload, indent=2, default=str))
        return True
    except Exception as exc:
        log.warning('could not persist design state for %s: %s', session_id, exc)
        return False


def load_design(session_id: str) -> Dict[str, Any]:
    try:
        p = _design_path(session_id)
        if p.is_file():
            return json.loads(p.read_text())
    except Exception as exc:
        log.warning('could not load design state for %s: %s', session_id, exc)
    return {}
