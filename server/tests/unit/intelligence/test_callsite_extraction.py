"""Unit tests for Python call-site extraction (AST-owned, unique ids)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from ai_agents.intelligence.parsers.python_ast import analyze_python_source


def analyze(text, path='mod.py'):
    return analyze_python_source(text, path)


def test_direct_and_method_calls():
    a = analyze('''
def validate():
    return True

def checkout():
    validate()
    obj.process(1)
''')
    calls = {(c['caller_qualname'], c['name'], c['call_type']) for c in a['call_sites']}
    assert ('checkout', 'validate', 'direct') in calls
    assert ('checkout', 'process', 'method') in calls
    m = next(c for c in a['call_sites'] if c['name'] == 'process')
    assert m['receiver'] == 'obj'
    assert m['receiver_root'] == 'obj'


def test_nested_function_calls_belong_to_inner():
    a = analyze('''
def outer():
    def inner():
        helper()
    inner()
''')
    inner_call = next(c for c in a['call_sites'] if c['name'] == 'helper')
    assert inner_call['caller_qualname'] == 'outer.inner'
    inner_call2 = next(c for c in a['call_sites'] if c['name'] == 'inner')
    assert inner_call2['caller_qualname'] == 'outer'
    # nested function has its own symbol id distinct from outer
    ids = {s['id'] for s in a['symbols']}
    assert 'mod.py::outer.inner' in ids
    assert 'mod.py::outer' in ids


def test_class_methods_have_qualified_ids():
    a = analyze('''
class A:
    def m(self):
        pass
class B:
    def m(self):
        pass
''')
    ids = {s['id'] for s in a['symbols']}
    assert 'mod.py::A.m' in ids
    assert 'mod.py::B.m' in ids
    assert 'mod.py::A.m' != 'mod.py::B.m'
    m = next(s for s in a['symbols'] if s['id'] == 'mod.py::A.m')
    assert m['kind'] == 'method'
    assert m['class_qualname'] == 'A'


def test_super_call_single_site():
    a = analyze('''
class Base:
    def process(self): pass
class Child(Base):
    def process(self):
        super().process()
''')
    sup = [c for c in a['call_sites'] if c['call_type'] == 'super']
    assert len(sup) == 1
    assert sup[0]['name'] == 'process'
    assert sup[0]['caller_qualname'] == 'Child.process'
    # no separate bare 'super' call site
    assert not any(c['name'] == 'super' and c['call_type'] == 'direct' for c in a['call_sites'])


def test_two_calls_same_target_preserved():
    a = analyze('''
def f():
    validate()
    validate()
''')
    vals = [c for c in a['call_sites'] if c['name'] == 'validate']
    assert len(vals) == 2
    assert vals[0]['callsite_id'] != vals[1]['callsite_id']


def test_kwargs_and_arg_count():
    a = analyze('''
def f():
    g(1, x=2)
''')
    c = next(c for c in a['call_sites'] if c['name'] == 'g')
    assert c['arg_count'] == 2


def test_dynamic_invocation_classified():
    a = analyze('''
def f(get_handler):
    get_handler()()
''')
    dyn = [c for c in a['call_sites'] if c['call_type'] == 'dynamic']
    assert len(dyn) >= 1


def test_self_attr_receiver():
    a = analyze('''
class Svc:
    def execute(self): pass
class App:
    def __init__(self):
        self.svc = Svc()
    def run(self):
        self.svc.execute()
''')
    c = next(c for c in a['call_sites'] if c['name'] == 'execute')
    assert c['receiver'] == 'self.svc'
    assert c['receiver_root'] == 'self'
    facts = a['scopes']['App.__init__']
    assert facts['self_attr_types'].get('svc') == ['Svc']


def test_local_type_assignment():
    a = analyze('''
def f():
    p = CardPayment()
    p.process(1)
''')
    facts = a['scopes']['f']
    assert facts['local_types'].get('p') == ['CardPayment']


def test_imports_carry_level_and_alias():
    a = analyze('''
from payments import validate as pv
from . import sibling
import os.path as p
''', 'pkg/mod.py')
    imps = {(i['kind'], i['name'], i['alias'], i['module'], i['level']) for i in a['imports']}
    assert ('from', 'validate', 'pv', 'payments', 0) in imps
    assert ('from', 'sibling', None, '', 1) in imps
    assert ('import', None, 'p', 'os.path', 0) in imps
    assert a['module_name'] == 'pkg.mod'


def test_signature_and_parameters():
    a = analyze('''
def f(self, amount: float, flag=True):
    pass
''')
    s = next(s for s in a['symbols'] if s['name'] == 'f')
    assert s['parameters'] == ['self', 'amount', 'flag']
    assert 'amount' in s['signature']
