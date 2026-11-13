"""Module-level CFG + reaching-definitions tests.

Covers build_module CFG extraction, module DefUseFacts, exit-state
reaching definitions, and their use by cross-module global propagation.
"""
import pytest

from ai_agents.intelligence.dataflow.cross_module import (
    CrossModuleAnalyzer, ModuleSummary)
from ai_agents.intelligence.dataflow.models import (
    DefUseFacts, Definition, VariableUse)
from ai_agents.intelligence.dataflow.repository_dfg import (
    _analyze_module_reaching, _module_facts)


def test_exit_defs_reassignment_kills_earlier():
    facts, exit_defs, _ = _analyze_module_reaching(
        'm.py', 'X = 1\nX = 2\n')
    assert exit_defs['X']['definition_ids'] == ['m.py::top::X:2:0']
    assert exit_defs['X']['definitely_assigned'] is True


def test_exit_defs_branches_both_reach():
    facts, exit_defs, _ = _analyze_module_reaching(
        'm.py', 'if c:\n    Y = 1\nelse:\n    Y = 2\n')
    ids = exit_defs['Y']['definition_ids']
    assert ids == ['m.py::top::Y:2:4', 'm.py::top::Y:4:4']
    # Assigned on every path (one branch or the other).
    assert exit_defs['Y']['definitely_assigned'] is True


def test_exit_defs_conditional_only_not_definite():
    facts, exit_defs, _ = _analyze_module_reaching(
        'm.py', 'if c:\n    Z = 1\n')
    assert 'Z' in exit_defs
    assert exit_defs['Z']['definitely_assigned'] is False


def test_exit_defs_unconditional_then_conditional():
    facts, exit_defs, _ = _analyze_module_reaching(
        'm.py', 'Z = 0\nif c:\n    Z = 1\n')
    ids = exit_defs['Z']['definition_ids']
    assert ids == ['m.py::top::Z:1:0', 'm.py::top::Z:3:4']
    assert exit_defs['Z']['definitely_assigned'] is True


def test_module_facts_have_cfg_nodes_and_uses():
    facts, exit_defs, _ = _analyze_module_reaching(
        'm.py', 'import os\nA = f(B)\nif cond:\n    C = A\n')
    # import and assignment definitions carry CFG node ids
    by_var = {d.variable: d for d in facts.definitions}
    assert by_var['os'].kind == 'import'
    assert by_var['os'].cfg_node_ids
    assert by_var['A'].cfg_node_ids
    # module-level reads are emitted as uses bound to CFG nodes
    uses = {(u.variable, u.line) for u in facts.uses}
    assert ('B', 2) in uses
    assert ('cond', 3) in uses
    assert ('A', 4) in uses
    for u in facts.uses:
        assert u.cfg_node_ids
        assert u.binding_key == 'm.py::%s' % u.variable


def test_module_facts_without_artifact_is_legacy():
    facts = _module_facts('m.py', 'X = 1\nY = X\n')
    assert {d.variable for d in facts.definitions} == {'X', 'Y'}
    assert facts.uses == []
    assert all(not d.cfg_node_ids for d in facts.definitions)


def test_del_kills_module_definition():
    facts, exit_defs, _ = _analyze_module_reaching(
        'm.py', 'X = 1\ndel X\n')
    assert 'X' not in exit_defs


def test_function_bodies_do_not_leak_into_module_facts():
    facts, exit_defs, _ = _analyze_module_reaching(
        'm.py',
        'X = 1\n'
        'def f():\n'
        '    X = 2\n'
        '    return X\n')
    top_x = [d for d in facts.definitions if d.variable == 'X']
    assert [d.line for d in top_x] == [1]
    assert exit_defs['X']['definition_ids'] == ['m.py::top::X:1:0']


# ------------------------------------------------------- cross-module exit defs

class _FakeResolver:
    def __init__(self, mapping):
        self.mapping = mapping

    def _resolve_import_target(self, imp, file_path, graph_ctx, depth=0):
        key = (imp.get('module'), imp.get('name'), imp.get('level', 0),
               imp.get('kind'))
        return self.mapping.get(key, (None, 'unresolved', ''))


def _definition(did, var, file, line, kind='assignment', binding=None,
                metadata=None):
    return Definition(id=did, variable=var, function_id=file, file=file,
                      line=line, column=0, kind=kind, cfg_node_ids=[],
                      binding_key=binding or '%s::%s' % (file, var),
                      metadata=metadata or {})


def _use(uid, var, file, line, func, binding):
    return VariableUse(id=uid, variable=var, function_id=func, file=file,
                       line=line, column=0, cfg_node_ids=[],
                       binding_key=binding)


def _summary(fid, top_ids, bindings):
    return ModuleSummary(module_id=fid, file_path=fid,
                         top_level_definitions=top_ids, global_writes=[],
                         imports=[], exports=[],
                         metadata={'import_bindings': bindings})


def _binding(local, module, name, kind, def_id, binding_key, scope=None,
             level=0):
    return {'importer_file': 'u.py', 'scope': scope or 'u.py',
            'local_name': local, 'import_module': module,
            'import_name': name, 'import_kind': kind,
            'import_level': level, 'binding_key': binding_key,
            'definition_id': def_id, 'line': 1}


def test_global_edge_uses_module_exit_definition():
    """A `from m import VAL` use resolves to m's module-exit definition."""
    u_facts = DefUseFacts(
        function_id='u.py', file='u.py',
        definitions=[_definition('u.py::top::VAL:1:0', 'VAL', 'u.py', 1,
                                 kind='import', binding='u.py::VAL',
                                 metadata={'import_module': 'm',
                                           'import_kind': 'from',
                                           'import_name': 'VAL',
                                           'import_level': 0})],
        uses=[_use('u.py::use::VAL:3:4', 'VAL', 'u.py', 3, 'u.py::f',
                   'u.py::VAL')])
    m_facts = DefUseFacts(
        function_id='m.py', file='m.py',
        definitions=[_definition('m.py::top::VAL:2:0', 'VAL', 'm.py', 2)])

    analyzer = CrossModuleAnalyzer(
        graph_ctx={'module_files': {}},
        resolver=_FakeResolver({('m', 'VAL', 0, 'from'):
                                (None, 'symbol', 'm.py')}))
    summaries = {
        'u.py': _summary('u.py', ['u.py::top::VAL:1:0'],
                         [_binding('VAL', 'm', 'VAL', 'from',
                                   'u.py::top::VAL:1:0', 'u.py::VAL')]),
        'm.py': _summary('m.py', ['m.py::top::VAL:2:0'], []),
    }
    result = analyzer.propagate_global_values(
        summaries, {'u.py': u_facts, 'm.py': m_facts},
        module_exit_defs={
            'u.py': {'VAL': {
                'definition_ids': ['u.py::top::VAL:1:0'],
                'definitely_assigned': True}},
            'm.py': {'VAL': {
                'definition_ids': ['m.py::top::VAL:2:0'],
                'definitely_assigned': True}}})

    edges = result['edges']
    assert len(edges) == 1
    assert edges[0]['source'] == 'm.py::top::VAL:2:0'
    assert edges[0]['target'] == 'u.py::use::VAL:3:4'
    assert edges[0]['resolution'] == 'confirmed'
    assert result['unresolved'] == []


def test_global_edge_ambiguous_exit_defs_emit_possible():
    """Multiple reaching exit definitions produce 'possible' edges."""
    u_facts = DefUseFacts(
        function_id='u.py', file='u.py',
        definitions=[_definition('u.py::top::VAL:1:0', 'VAL', 'u.py', 1,
                                 kind='import', binding='u.py::VAL',
                                 metadata={'import_module': 'm',
                                           'import_kind': 'from',
                                           'import_name': 'VAL',
                                           'import_level': 0})],
        uses=[_use('u.py::use::VAL:3:4', 'VAL', 'u.py', 3, 'u.py::f',
                   'u.py::VAL')])
    m_facts = DefUseFacts(
        function_id='m.py', file='m.py',
        definitions=[
            _definition('m.py::top::VAL:2:4', 'VAL', 'm.py', 2),
            _definition('m.py::top::VAL:4:4', 'VAL', 'm.py', 4),
        ])
    analyzer = CrossModuleAnalyzer(
        graph_ctx={'module_files': {}},
        resolver=_FakeResolver({('m', 'VAL', 0, 'from'):
                                (None, 'symbol', 'm.py')}))
    summaries = {
        'u.py': _summary('u.py', ['u.py::top::VAL:1:0'],
                         [_binding('VAL', 'm', 'VAL', 'from',
                                   'u.py::top::VAL:1:0', 'u.py::VAL')]),
        'm.py': _summary('m.py', ['m.py::top::VAL:2:4',
                                  'm.py::top::VAL:4:4'], []),
    }
    result = analyzer.propagate_global_values(
        summaries, {'u.py': u_facts, 'm.py': m_facts},
        module_exit_defs={
            'u.py': {'VAL': {
                'definition_ids': ['u.py::top::VAL:1:0'],
                'definitely_assigned': True}},
            'm.py': {'VAL': {
                'definition_ids': ['m.py::top::VAL:2:4',
                                   'm.py::top::VAL:4:4'],
                'definitely_assigned': True}}})
    assert {e['resolution'] for e in result['edges']} == {'possible'}
    assert {e['source'] for e in result['edges']} == {
        'm.py::top::VAL:2:4', 'm.py::top::VAL:4:4'}


def test_global_edge_missing_exit_def_is_unresolved():
    """When exit-def analysis ran but has no entry, no heuristic fallback."""
    u_facts = DefUseFacts(
        function_id='u.py', file='u.py',
        definitions=[_definition('u.py::top::VAL:1:0', 'VAL', 'u.py', 1,
                                 kind='import', binding='u.py::VAL',
                                 metadata={'import_module': 'm',
                                           'import_kind': 'from',
                                           'import_name': 'VAL',
                                           'import_level': 0})],
        uses=[_use('u.py::use::VAL:3:4', 'VAL', 'u.py', 3, 'u.py::f',
                   'u.py::VAL')])
    m_facts = DefUseFacts(
        function_id='m.py', file='m.py',
        definitions=[_definition('m.py::top::OTHER:2:0', 'OTHER', 'm.py', 2)])
    analyzer = CrossModuleAnalyzer(
        graph_ctx={'module_files': {}},
        resolver=_FakeResolver({('m', 'VAL', 0, 'from'):
                                (None, 'symbol', 'm.py')}))
    summaries = {
        'u.py': _summary('u.py', ['u.py::top::VAL:1:0'],
                         [_binding('VAL', 'm', 'VAL', 'from',
                                   'u.py::top::VAL:1:0', 'u.py::VAL')]),
        'm.py': _summary('m.py', ['m.py::top::OTHER:2:0'], []),
    }
    result = analyzer.propagate_global_values(
        summaries, {'u.py': u_facts, 'm.py': m_facts},
        module_exit_defs={
            'u.py': {'VAL': {
                'definition_ids': ['u.py::top::VAL:1:0'],
                'definitely_assigned': True}},
            'm.py': {}})
    assert result['edges'] == []
    assert any('no module-exit definition' in u['reason']
               for u in result['unresolved'])


def test_module_reassignment_edge_prefers_local_rebind():
    """`from m import VAL` then `VAL = 5` at module level: uses connect to
    the reassignment definition, not the import or m's definition."""
    u_facts = DefUseFacts(
        function_id='u.py', file='u.py',
        definitions=[
            _definition('u.py::top::VAL:1:0', 'VAL', 'u.py', 1,
                        kind='import', binding='u.py::VAL',
                        metadata={'import_module': 'm',
                                  'import_kind': 'from',
                                  'import_name': 'VAL',
                                  'import_level': 0}),
            _definition('u.py::top::VAL:2:0', 'VAL', 'u.py', 2),
        ],
        uses=[_use('u.py::use::VAL:4:4', 'VAL', 'u.py', 4, 'u.py::f',
                   'u.py::VAL')])
    m_facts = DefUseFacts(
        function_id='m.py', file='m.py',
        definitions=[_definition('m.py::top::VAL:2:0', 'VAL', 'm.py', 2)])
    analyzer = CrossModuleAnalyzer(
        graph_ctx={'module_files': {}},
        resolver=_FakeResolver({('m', 'VAL', 0, 'from'):
                                (None, 'symbol', 'm.py')}))
    summaries = {
        'u.py': _summary('u.py', ['u.py::top::VAL:1:0',
                                  'u.py::top::VAL:2:0'],
                         [_binding('VAL', 'm', 'VAL', 'from',
                                   'u.py::top::VAL:1:0', 'u.py::VAL')]),
        'm.py': _summary('m.py', ['m.py::top::VAL:2:0'], []),
    }
    result = analyzer.propagate_global_values(
        summaries, {'u.py': u_facts, 'm.py': m_facts},
        module_exit_defs={
            'u.py': {'VAL': {
                'definition_ids': ['u.py::top::VAL:2:0'],
                'definitely_assigned': True}},
            'm.py': {'VAL': {
                'definition_ids': ['m.py::top::VAL:2:0'],
                'definitely_assigned': True}}})
    assert len(result['edges']) == 1
    assert result['edges'][0]['source'] == 'u.py::top::VAL:2:0'
    assert result['edges'][0]['via'] == 'reassignment'
    assert result['edges'][0]['resolution'] == 'confirmed'


# ------------------------------------------------- same-line assignment identity

def test_same_line_assignments_bind_to_own_commit_nodes():
    """`X = 1; Y = X; X = 3` — three assignments on one line must map to
    three distinct commit nodes; the Y = X use reaches only the first X."""
    import ast
    from ai_agents.intelligence.controlflow.python_cfg import (
        PythonCFGBuilder)
    from ai_agents.intelligence.dataflow.reaching_definitions import (
        ReachingDefinitionsAnalyzer, reaching_definition_ids)

    source = 'X = 1; Y = X; X = 3\n'
    tree = ast.parse(source)
    artifact = PythonCFGBuilder().build_module(
        tree, 'm.py', source, 'm.py')
    facts = _module_facts('m.py', source, artifact=artifact, tree=tree)

    x_defs = [d for d in facts.definitions if d.variable == 'X']
    assert len(x_defs) == 2
    first_ids = set(x_defs[0].cfg_node_ids)
    second_ids = set(x_defs[1].cfg_node_ids)
    assert first_ids and second_ids
    assert not (first_ids & second_ids)

    commit_ids = {n.id for n in artifact.graph.nodes
                  if n.metadata.get('is_commit')}
    assert first_ids <= commit_ids
    assert second_ids <= commit_ids

    # The `Y = X` read is a single use of X on line 1.
    x_uses = [u for u in facts.uses if u.variable == 'X' and u.line == 1]
    assert len(x_uses) == 1
    use = x_uses[0]
    # Its CFG node is the evaluation node of the `Y = X` statement, not a
    # commit node of either X assignment.
    assert use.cfg_node_ids
    assert not (set(use.cfg_node_ids) & (first_ids | second_ids))

    analysis = ReachingDefinitionsAnalyzer().analyze(
        artifact.graph, facts)
    reached = reaching_definition_ids(analysis, facts, use)
    assert x_defs[0].id in reached
    assert x_defs[1].id not in reached


# --------------------------------------- definition-time header expressions

def test_function_decorator_and_defaults_emit_module_uses():
    facts, _, _ = _analyze_module_reaching(
        'm.py',
        'LIMIT = 10\n'
        'MODE = "r"\n'
        'def register(f):\n'
        '    return f\n'
        '@register\n'
        'def process(limit=LIMIT, *, mode=MODE):\n'
        '    pass\n')
    uses = {(u.variable, u.line) for u in facts.uses}
    assert ('register', 5) in uses
    assert ('LIMIT', 6) in uses
    assert ('MODE', 6) in uses


def test_class_decorator_bases_metaclass_emit_module_uses():
    facts, _, _ = _analyze_module_reaching(
        'm.py',
        'def cdec(c):\n'
        '    return c\n'
        'class Base:\n'
        '    pass\n'
        'class Meta(type):\n'
        '    pass\n'
        '@cdec\n'
        'class C(Base, metaclass=Meta):\n'
        '    pass\n')
    uses = {(u.variable, u.line) for u in facts.uses}
    assert ('cdec', 7) in uses
    assert ('Base', 8) in uses
    assert ('Meta', 8) in uses


def test_annotations_are_uses_without_future_import():
    facts, _, _ = _analyze_module_reaching(
        'm.py',
        'T = int\n'
        'R = str\n'
        'def f(x: T) -> R:\n'
        '    pass\n')
    uses = {(u.variable, u.line) for u in facts.uses}
    assert ('T', 3) in uses
    assert ('R', 3) in uses


def test_postponed_annotations_are_not_runtime_reads():
    facts, _, _ = _analyze_module_reaching(
        'm.py',
        'from __future__ import annotations\n'
        'T = int\n'
        'R = str\n'
        'def f(x: T) -> R:\n'
        '    pass\n')
    uses = {(u.variable, u.line) for u in facts.uses}
    assert ('T', 4) not in uses
    assert ('R', 4) not in uses
