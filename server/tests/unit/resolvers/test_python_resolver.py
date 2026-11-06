"""Unit tests for PythonResolver against in-memory graph contexts."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from ai_agents.intelligence.resolvers.python_resolver import PythonResolver
from ai_agents.intelligence.resolvers.base import (
    STATUS_STATIC_RESOLVED, STATUS_DYNAMIC, STATUS_EXTERNAL, STATUS_UNRESOLVED,
)


def make_ctx(files):
    """files: {rel_path: source}. Returns (resolver, graph_ctx, file_ctxs)."""
    from ai_agents.intelligence.parsers.python_ast import analyze_python_source
    resolver = PythonResolver()
    analyses = {rel: analyze_python_source(text, rel) for rel, text in files.items()}
    nodes, symbol_by_id, node_ids = [], {}, set()
    module_files, file_symbols, class_by_name, classes_info = {}, {}, {}, {}
    for rel, a in analyses.items():
        file_symbols[rel] = a['symbols']
        mod = a.get('module_name')
        if mod:
            module_files[mod] = rel
        for sym in a['symbols']:
            sid = sym['id']
            node = dict(sym)
            node['level'] = 'class' if sym['kind'] == 'object' else 'function'
            nodes.append(node)
            symbol_by_id[sid] = node
            node_ids.add(sid)
            if sym['kind'] == 'object':
                class_by_name.setdefault(sym['name'], []).append(sid)
                classes_info[sid] = {'name': sym['name'], 'qualname': sym['qualname'],
                                     'file': rel, 'bases': sym.get('bases', []), 'base_ids': []}
    # resolve bases
    for sid, info in classes_info.items():
        for b in info['bases']:
            info['base_ids'] += resolver.resolve_base_class_ids([b], info['file'],
                {'class_by_name': class_by_name, 'symbol_by_id': symbol_by_id,
                 'module_files': module_files, 'nodes': nodes, 'node_ids': node_ids})
    subclasses = {}
    for sid, info in classes_info.items():
        for b in info['base_ids']:
            subclasses.setdefault(b, []).append(sid)
    graph_ctx = {'nodes': nodes, 'node_ids': node_ids, 'symbol_by_id': symbol_by_id,
                 'module_files': module_files, 'file_symbols': file_symbols,
                 'analyses': analyses, 'class_by_name': class_by_name,
                 'classes_info': classes_info, 'subclasses': subclasses}
    file_ctxs = {rel: resolver.build_context(rel, text, nodes, analyses[rel])
                 for rel, text in files.items()}
    return resolver, graph_ctx, file_ctxs, analyses


def call_for(analysis, name, caller=None):
    for c in analysis['call_sites']:
        if c['name'] == name and (caller is None or c['caller_qualname'] == caller):
            return c
    raise AssertionError(f'call {name} in {caller} not found')


def test_same_file_direct_call():
    files = {'a.py': 'def validate():\n    return True\n\ndef checkout():\n    return validate()\n'}
    r, ctx, fcs, analyses = make_ctx(files)
    call = call_for(analyses['a.py'], 'validate', 'checkout')
    res = r.resolve(call, fcs['a.py'], ctx)
    assert res.status == STATUS_STATIC_RESOLVED
    assert res.targets == ['a.py::validate']


def test_import_alias():
    files = {
        'payments.py': 'def validate(x):\n    return True\n',
        'main.py': 'from payments import validate as pv\n\ndef checkout():\n    return pv(1)\n',
    }
    r, ctx, fcs, analyses = make_ctx(files)
    call = call_for(analyses['main.py'], 'pv', 'checkout')
    res = r.resolve(call, fcs['main.py'], ctx)
    assert res.status == STATUS_STATIC_RESOLVED
    assert res.targets == ['payments.py::validate']


def test_self_method():
    files = {'p.py': '''class Card:
    def validate(self):
        return True
    def process(self):
        return self.validate()
'''}
    r, ctx, fcs, analyses = make_ctx(files)
    call = call_for(analyses['p.py'], 'validate', 'Card.process')
    res = r.resolve(call, fcs['p.py'], ctx)
    assert res.status == STATUS_STATIC_RESOLVED
    assert res.targets == ['p.py::Card.validate']


def test_super_method():
    files = {'p.py': '''class Base:
    def process(self):
        pass
class Child(Base):
    def process(self):
        super().process()
'''}
    r, ctx, fcs, analyses = make_ctx(files)
    call = call_for(analyses['p.py'], 'process', 'Child.process')
    assert call['call_type'] == 'super'
    res = r.resolve(call, fcs['p.py'], ctx)
    assert res.status == STATUS_STATIC_RESOLVED
    assert res.targets == ['p.py::Base.process']


def test_typed_receiver_polymorphic():
    files = {'p.py': '''class Payment:
    def process(self): pass
class Card(Payment):
    def process(self): pass
class Upi(Payment):
    def process(self): pass
def checkout(payment: Payment):
    payment.process()
'''}
    r, ctx, fcs, analyses = make_ctx(files)
    call = call_for(analyses['p.py'], 'process', 'checkout')
    res = r.resolve(call, fcs['p.py'], ctx)
    assert res.status in ('polymorphic', 'static_resolved')
    assert 'p.py::Card.process' in (res.targets + res.candidates)
    assert 'p.py::Upi.process' in (res.targets + res.candidates)


def test_dynamic_getattr():
    files = {'a.py': 'def f(obj):\n    return getattr(obj, "x")()\n'}
    r, ctx, fcs, analyses = make_ctx(files)
    # getattr(...)() is a dynamic invocation
    dyn = [c for c in analyses['a.py']['call_sites'] if c['call_type'] == 'dynamic']
    assert dyn, 'expected a dynamic call site'
    res = r.resolve(dyn[0], fcs['a.py'], ctx)
    assert res.status == STATUS_DYNAMIC


def test_external_import():
    files = {'a.py': 'import requests\n\ndef f(url):\n    return requests.get(url)\n'}
    r, ctx, fcs, analyses = make_ctx(files)
    call = call_for(analyses['a.py'], 'get', 'f')
    res = r.resolve(call, fcs['a.py'], ctx)
    assert res.status == STATUS_EXTERNAL


def test_recursive_call():
    files = {'a.py': 'def rec(n):\n    if n: rec(n-1)\n'}
    r, ctx, fcs, analyses = make_ctx(files)
    call = call_for(analyses['a.py'], 'rec', 'rec')
    res = r.resolve(call, fcs['a.py'], ctx)
    assert res.status == STATUS_STATIC_RESOLVED
    assert res.targets == ['a.py::rec']


def test_unresolved_no_fabrication():
    files = {'a.py': 'def f():\n    return does_not_exist()\n'}
    r, ctx, fcs, analyses = make_ctx(files)
    call = call_for(analyses['a.py'], 'does_not_exist', 'f')
    res = r.resolve(call, fcs['a.py'], ctx)
    assert res.status in (STATUS_UNRESOLVED, 'ambiguous')
    assert res.targets == []


def test_function_local_import_does_not_leak():
    """P0 regression: an import inside function_a must not bind in function_b."""
    files = {'a.py': 'def function_a():\n    from payments import process\n    process()\n\ndef function_b():\n    process()\n',
             'payments.py': 'def process():\n    pass\n'}
    r, ctx, fcs, analyses = make_ctx(files)
    call_a = call_for(analyses['a.py'], 'process', 'function_a')
    call_b = call_for(analyses['a.py'], 'process', 'function_b')
    res_a = r.resolve(call_a, fcs['a.py'], ctx)
    res_b = r.resolve(call_b, fcs['a.py'], ctx)
    assert res_a.status == STATUS_STATIC_RESOLVED
    assert res_a.targets == ['payments.py::process']
    # function_b has no such import -> must NOT resolve to payments.process
    assert res_b.status != STATUS_STATIC_RESOLVED or res_b.targets != ['payments.py::process']


def test_forward_reference_same_file():
    """P0 regression: a def later in the file is visible to earlier calls."""
    files = {'a.py': 'def checkout():\n    return validate()\n\ndef validate():\n    return True\n'}
    r, ctx, fcs, analyses = make_ctx(files)
    call = call_for(analyses['a.py'], 'validate', 'checkout')
    res = r.resolve(call, fcs['a.py'], ctx)
    assert res.status == STATUS_STATIC_RESOLVED
    assert res.targets == ['a.py::validate']


def test_c3_mro_multiple_inheritance():
    """P0: proper C3 order for diamond inheritance."""
    files = {'m.py': '''class A:
    def who(self): return 'A'
class B(A):
    def who(self): return 'B'
class C(A):
    pass
class D(B, C):
    def who(self):
        return super().who()
''' }
    r, ctx, fcs, analyses = make_ctx(files)
    mro = r._mro('m.py::D', ctx)
    # C3: D, B, C, A  (B before C because declared first in bases)
    assert mro == ['m.py::D', 'm.py::B', 'm.py::C', 'm.py::A']
    call = call_for(analyses['m.py'], 'who', 'D.who')
    res = r.resolve(call, fcs['m.py'], ctx)
    assert res.status == STATUS_STATIC_RESOLVED
    assert res.targets == ['m.py::B.who']
