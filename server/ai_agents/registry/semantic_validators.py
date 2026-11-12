"""Semantic (cross-argument / filesystem) validation for tool contracts.

JSON schemas cannot compare two arguments or touch the filesystem, so these
rules run after schema validation on both call arguments and results.
Validation fails closed: a rule that raises is itself an error.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List

# Per-tool argument rules: each returns an error string or None.
ARG_RULES: Dict[str, List] = {
    'read_file_range': [
        lambda a: 'start_line must be <= end_line'
        if a.get('start_line', 0) > a.get('end_line', 0) else None],
}

# Per-tool result rules.
RESULT_RULES: Dict[str, List] = {
    'read_file_range': [
        lambda r: 'end_line < start_line'
        if r.get('status') == 'ok' and r.get('end_line', 0) < r.get('start_line', 0)
        else None],
}

# ----------------------------------------------------------------------
# Per-tool path policies (audit 2.7): which arguments are paths and which
# root they must stay inside.
#   'active_repository'  -> config.REPO_ROOT (main checkout)
#   'active_worktree'    -> the worktree the tool operates on
#   'registered_repository' -> a repository registered under REPOSITORY_DIR
# ----------------------------------------------------------------------
PATH_POLICIES: Dict[str, Dict[str, str]] = {
    'read_file': {'file_path': 'active_repository'},
    'read_file_range': {'file_path': 'active_repository'},
    'search_code': {'file_path': 'active_repository',
                    'path': 'active_repository'},
    'list_files': {'directory': 'active_repository',
                   'path': 'active_repository'},
    'extract_symbols': {'file_path': 'active_repository'},
    'parse_source_code': {'file_path': 'active_repository'},
    'extract_function': {'file_path': 'active_repository'},
    'get_imports': {'file_path': 'active_repository'},
    'get_exports': {'file_path': 'active_repository'},
    'get_scope_information': {'file_path': 'active_repository'},
    'resolve_types': {'file_path': 'active_repository'},
    'edit_file': {'file_path': 'active_repository'},
    'apply_patch': {'file_path': 'active_repository'},
    'search_and_replace': {'file_pattern': 'active_repository'},
    'run_tests': {'test_files': 'active_worktree'},
    'run_unit_tests': {'test_files': 'active_worktree'},
    'run_integration_tests': {'test_files': 'active_worktree'},
    'run_regression_tests': {'test_files': 'active_worktree'},
    'verify_compilation': {'file_path': 'active_worktree'},
    'verify_lint': {'file_path': 'active_worktree'},
    'verify_types': {'file_path': 'active_worktree'},
    'open_repository': {'repository_path': 'registered_repository'},
    'open_vr_repository': {'repository_path': 'registered_repository'},
    'get_repository_metadata': {'repository_path': 'registered_repository'},
    'git_status': {'repository_path': 'registered_repository'},
    'git_diff': {'repository_path': 'registered_repository',
                 'file_path': 'registered_repository'},
    'git_branch': {'repository_path': 'registered_repository'},
    'read_worktree_file': {'file_path': 'active_worktree'},
    'apply_patch_to_worktree': {'file_path': 'active_worktree',
                                'target_file': 'active_worktree',
                                'patch_file': 'active_worktree'},
    'get_worktree_diff': {'file_path': 'active_worktree'},
    'get_source': {'file_path': 'active_repository'},
    'search_symbols': {'path': 'active_repository',
                       'directory': 'active_repository'},
    'find_tests_for_node': {'test_path': 'active_repository'},
    'run_security_scan': {'files': 'active_worktree'},
    'create_worktree': {'repository_path': 'registered_repository'},
}


def _validate_runtime_command(args):
    """start_runtime_trace takes a command list, not paths: every element
    used to be treated as a path by PATH_POLICIES, which rejected valid
    argv like ['script.py', '--flag']. Containment of command[0] is verified
    against the real trace root inside the tool itself."""
    cmd = args.get('command')
    if not isinstance(cmd, list) or not cmd \
            or not all(isinstance(c, str) for c in cmd):
        return ['command must be a non-empty list of strings']
    if len(cmd) > 32 or any(len(c) > 512 for c in cmd):
        return ['command too long']
    script = cmd[0]
    if Path(script).is_absolute() or not script.endswith('.py'):
        return ['command[0] must be a relative .py path']
    return []        # containment is verified against the real root inside the tool


def _roots(scope: str):
    """Permitted roots for a path-policy scope."""
    from ..tools._common import repo_root
    from .. import config
    if scope == 'active_repository':
        return [repo_root().resolve()]
    if scope == 'active_worktree':
        roots = []
        wt = getattr(config, 'ACTIVE_WORKTREE', None)
        if wt:
            roots.append(__import__('pathlib').Path(wt).resolve())
        # Worktrees legitimately live outside the main checkout; allow any
        # path that stays inside a registered worktree root when configured,
        # otherwise fall back to the repository root.
        roots.extend(_registered_worktrees())
        return roots or [repo_root().resolve()]
    if scope == 'registered_repository':
        return _registered_repositories()
    return []


def _registered_repositories():
    from pathlib import Path
    from .. import config
    out = []
    base = getattr(config, 'REPOSITORY_DIR', None)
    if base:
        for child in Path(base).iterdir():
            if child.is_dir():
                out.append(child.resolve())
    return out


def _registered_worktrees():
    from pathlib import Path
    from .. import config
    out = []
    base = getattr(config, 'WORKTREE_DIR', None) or getattr(
        config, 'REPOSITORY_DIR', None)
    if base:
        try:
            for child in Path(base).rglob('.git'):
                out.append(child.parent.resolve())
        except Exception:
            pass
    return out


def _resolve_candidate(raw):
    """Resolve one path value (or each element of a list) to absolute paths,
    following symlinks before any containment check."""
    from pathlib import Path
    values = raw if isinstance(raw, (list, tuple)) else [raw]
    out = []
    for v in values:
        if not isinstance(v, str) or not v.strip():
            continue
        p = Path(v).expanduser()
        if not p.is_absolute():
            try:
                from ..tools._common import repo_root
                p = repo_root() / p
            except Exception:
                p = Path.cwd() / p
        try:
            out.append(p.resolve())
        except Exception:
            out.append(p.absolute())
    return out


def _inside_any(path, roots):
    for root in roots:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _path_errors(tool_name: str, args: Dict[str, Any]) -> List[str]:
    """Enforce PATH_POLICIES for one tool's arguments."""
    errors = []
    policies = PATH_POLICIES.get(tool_name) or {}
    for param, scope in policies.items():
        raw = args.get(param)
        if raw is None:
            continue
        if scope == 'registered_repository':
            # Selection validation: the path must name a registered repo.
            for p in _resolve_candidate(raw):
                if not _inside_any(p, _registered_repositories()) \
                        and p not in _registered_repositories():
                    errors.append(
                        '%s must select a registered repository: %s'
                        % (param, raw))
            continue
        roots = _roots(scope)
        for p in _resolve_candidate(raw):
            if roots and not _inside_any(p, roots):
                errors.append(
                    '%s escapes the permitted root (%s): %s'
                    % (param, scope, raw))
    return errors


def semantic_errors(tool_name: str, args: Dict[str, Any]) -> List[str]:
    """Argument rules: per-tool path policies, then per-tool rules."""
    errors = []
    errors.extend(_path_errors(tool_name, args or {}))
    if tool_name == 'start_runtime_trace':
        errors.extend(_validate_runtime_command(args or {}))
    for rule in ARG_RULES.get(tool_name, []):
        try:
            msg = rule(args or {})
        except Exception as exc:
            errors.append(
                'Semantic validation failed for %s: %s' % (tool_name, exc))
            continue
        if msg:
            errors.append(msg)
    return errors


# ----------------------------------------------------------------------
# Result (output) semantic rules per tool family.
# ----------------------------------------------------------------------
def _graph_edges_reference_nodes(result):
    edges = result.get('edges')
    if not isinstance(edges, list) or not edges:
        return None
    if result.get('status') not in ('ok', 'completed', 'partial'):
        return None
    nodes = result.get('nodes')
    if not isinstance(nodes, list) or not nodes:
        return 'graph has edges but no node list'
    ids = []
    for n in nodes:
        nid = n.get('id') if isinstance(n, dict) else n
        if not nid:
            return 'node without id'
        ids.append(nid)
    if len(ids) != len(set(ids)):
        return 'duplicate node ids'
    idset, bad = set(ids), 0
    for e in edges:
        if not isinstance(e, dict):
            return 'edge is not an object'
        s = e.get('source', e.get('src'))
        t = e.get('target', e.get('dst'))
        if not s or not t:
            return 'edge missing source or target'
        if s not in idset or t not in idset:
            bad += 1
        if e.get('resolution') == 'confirmed' and not e.get('kind'):
            return 'confirmed edge without kind'
    return '%d edge(s) reference missing nodes' % bad if bad else None


def _call_graph_confirmed_resolved(result):
    edges = result.get('edges') or result.get('call_graph', {}).get('edges') \
        if isinstance(result.get('call_graph'), dict) else result.get('edges')
    if not isinstance(edges, list):
        return None
    bad = [e for e in edges if isinstance(e, dict)
           and e.get('resolution') == 'confirmed'
           and not (e.get('target') or e.get('to') or e.get('callee'))]
    return ('%d confirmed edge(s) lack a resolved target' % len(bad)
            if bad else None)


def _dfg_endpoints_have_evidence(result):
    graph = result.get('graph')
    if not isinstance(graph, dict):
        return None
    edges, nodes = graph.get('edges'), graph.get('nodes') or []
    if not isinstance(edges, list):
        return None
    ids = {n.get('id') if isinstance(n, dict) else n for n in nodes}
    bad = 0
    for e in edges:
        if not isinstance(e, dict) or e.get('resolution') != 'confirmed':
            continue
        ev = e.get('evidence') or {}
        ok = (e.get('source') and e.get('target') and e.get('kind')
              and (not ids or (e['source'] in ids and e['target'] in ids))
              and isinstance(ev, dict)
              and (ev.get('source_file') or ev.get('file'))
              and (ev.get('source_line') or ev.get('line'))
              and (ev.get('target_file') or ev.get('file'))
              and (ev.get('target_line') or ev.get('line')))
        if not ok:
            bad += 1
    return ('%d confirmed DFG edge(s) lack source/target evidence' % bad
            if bad else None)


def _test_counts_consistent(result):
    if result.get('status') not in ('ok', 'passed', 'failed'):
        return None
    def n(k):
        v = result.get(k)
        return len(v) if isinstance(v, list) else (v if isinstance(v, int) else 0)
    p, f, s_, nr = n('passed'), n('failed'), n('skipped'), n('not_run')
    total = result.get('total')
    if isinstance(total, int) and total != p + f + s_ + nr:
        return 'total %d != passed+failed+skipped+not_run %d' % (
            total, p + f + s_ + nr)
    if f > 0 and result.get('status') in ('ok', 'passed'):
        return 'failed tests reported in a passing run'
    ec = result.get('exit_code')
    if isinstance(ec, int) and ec != 0 and result.get('status') in ('ok', 'passed'):
        return 'non-zero exit code reported as success'
    return None


def _review_acceptance_coverage(result):
    if result.get('verdict') not in ('approve', 'request_changes', 'block'):
        return None
    findings = result.get('findings')
    if findings is None:
        return None
    acceptance = result.get('acceptance')
    if acceptance is not None and not isinstance(acceptance, list):
        return 'acceptance must be a list'
    # Every declared acceptance criterion must appear in the review's
    # acceptance coverage when the producer supplies the criteria list.
    criteria = result.get('acceptance_criteria') or result.get('criteria')
    if isinstance(criteria, list) and isinstance(acceptance, list):
        blob = json.dumps(acceptance, default=str).lower()
        missing = [str(c) for c in criteria
                   if str(c).strip() and str(c).lower() not in blob]
        if missing:
            return '%d acceptance criterion/criteria not covered: %s' % (
                len(missing), '; '.join(missing[:3]))
    return None


def _runtime_events_valid(result):
    evs = result.get('events')
    if not isinstance(evs, list):
        return None
    last = 0
    for e in evs:
        if not isinstance(e, dict):
            return 'event is not an object'
        if e.get('kind') not in ('call', 'return', 'exception'):
            return 'invalid event kind %r' % e.get('kind')
        if not e.get('file') or not isinstance(e.get('line'), int):
            return 'event %s missing source location' % e.get('sequence')
        if e.get('sequence', 0) <= last:
            return 'event sequence not increasing'
        last = e['sequence']
    return None


def _node_id_set(result):
    """Collect node ids from the shapes graph results use."""
    ids = set()
    for container in (result, result.get('graph')
                      if isinstance(result.get('graph'), dict) else {},
                      result.get('cfg') if isinstance(result.get('cfg'), dict)
                      else {}):
        nodes = container.get('nodes')
        if isinstance(nodes, list):
            for n in nodes:
                nid = n.get('id') if isinstance(n, dict) else n
                if nid:
                    ids.add(nid)
    return ids


def _edge_endpoints_ok(e, idset):
    s = e.get('source', e.get('src'))
    t = e.get('target', e.get('dst'))
    if not s or not t:
        return False
    return not idset or (s in idset and t in idset)


def _cfg_branches_valid(result):
    """Every CFG branch edge endpoint must be a known CFG node."""
    branches = result.get('branches')
    edges = result.get('edges')
    if branches is None and edges is None:
        graph = result.get('graph')
        if isinstance(graph, dict):
            edges = graph.get('edges')
    edge_list = branches if isinstance(branches, list) else edges
    if not isinstance(edge_list, list) or not edge_list:
        return None
    idset = _node_id_set(result)
    bad = sum(1 for e in edge_list
              if isinstance(e, dict) and not _edge_endpoints_ok(e, idset))
    return '%d CFG edge(s) reference missing nodes' % bad if bad else None


def _arch_relationships_valid(result):
    """Every architecture relationship endpoint must name a component id."""
    arch = result.get('architecture')
    if not isinstance(arch, dict):
        arch = result if 'components' in result else None
    if not isinstance(arch, dict):
        return None
    comps = arch.get('components')
    rels = arch.get('relationships')
    if not isinstance(comps, list) or not isinstance(rels, list):
        return None
    ids = {c.get('id') for c in comps if isinstance(c, dict)}
    ids.discard(None)
    bad = 0
    for r in rels:
        if not isinstance(r, dict):
            return 'relationship is not an object'
        src = r.get('source', r.get('src'))
        dst = r.get('target', r.get('dst'))
        if src not in ids or dst not in ids:
            bad += 1
    return '%d relationship(s) reference missing components' % bad         if bad else None


def _security_findings_valid(result):
    findings = result.get('findings')
    if not isinstance(findings, list):
        return None
    bad = 0
    for f in findings:
        if not isinstance(f, dict):
            return 'finding is not an object'
        if not f.get('file') or not isinstance(f.get('line'), int)                 or f.get('line') < 1:
            bad += 1
    return '%d security finding(s) lack file/line' % bad if bad else None


RESULT_RULES['get_runtime_trace'] = [_runtime_events_valid]

# Family -> result rules. Tools not listed still get the generic graph rule
# when their result carries nodes+edges.
_FAMILY_RESULT_RULES: Dict[str, List] = {
    'build_call_graph': [_call_graph_confirmed_resolved,
                         _graph_edges_reference_nodes],
    'build_dependency_graph': [_graph_edges_reference_nodes],
    'query_graph_path': [_graph_edges_reference_nodes],
    'find_circular_dependencies': [_graph_edges_reference_nodes],
    'trace_call_chain': [_graph_edges_reference_nodes],
    'build_data_flow_graph': [_dfg_endpoints_have_evidence,
                              _graph_edges_reference_nodes],
    'trace_cross_function_flow': [_graph_edges_reference_nodes],
    'analyze_control_flow': [_cfg_branches_valid,
                             _graph_edges_reference_nodes],
    'visualize_call_graph': [_graph_edges_reference_nodes],
    'visualize_dependency_graph': [_graph_edges_reference_nodes],
    'visualize_control_flow': [_graph_edges_reference_nodes],
    'visualize_data_flow': [_graph_edges_reference_nodes],
    'visualize_unified_graph': [_graph_edges_reference_nodes],
    'visualize_change_impact': [_graph_edges_reference_nodes],
    'run_tests': [_test_counts_consistent],
    'run_unit_tests': [_test_counts_consistent],
    'run_integration_tests': [_test_counts_consistent],
    'run_regression_tests': [_test_counts_consistent],
    'read_test_results': [_test_counts_consistent],
    'merge_agent_results': [_review_acceptance_coverage],
    'resolve_conflicting_findings': [_review_acceptance_coverage],
    'propose_architecture': [_arch_relationships_valid],
    'get_proposed_architecture': [_arch_relationships_valid],
    'add_component': [_arch_relationships_valid],
    'remove_component': [_arch_relationships_valid],
    'update_component': [_arch_relationships_valid],
    'add_relationship': [_arch_relationships_valid],
    'remove_relationship': [_arch_relationships_valid],
    'update_relationship': [_arch_relationships_valid],
    'validate_architecture': [_arch_relationships_valid],
    'run_security_scan': [_security_findings_valid],
}

# Generic fallback: any result with both nodes and edges gets the graph rule.
_GENERIC_RESULT_RULES = [_graph_edges_reference_nodes]


def _rules_for(tool_name: str) -> List:
    rules = list(RESULT_RULES.get(tool_name, []))
    rules.extend(_FAMILY_RESULT_RULES.get(tool_name, []))
    if not _FAMILY_RESULT_RULES.get(tool_name):
        rules.extend(_GENERIC_RESULT_RULES)
    return rules


def semantic_result_errors(tool_name: str, result: Any) -> List[str]:
    """Result rules: per-tool checks that need more than a schema."""
    errors = []
    if not isinstance(result, dict):
        return errors
    for rule in _rules_for(tool_name):
        try:
            msg = rule(result)
        except Exception as exc:
            errors.append(
                'Semantic validation failed for %s: %s' % (tool_name, exc))
            continue
        if msg:
            errors.append(msg)
    return errors
