"""Unit tests for the structural JavaScript/TypeScript resolver."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from ai_agents.intelligence.resolvers.javascript_resolver import JavaScriptResolver
from ai_agents.intelligence.resolvers.base import (
    STATUS_STATIC_RESOLVED, STATUS_UNRESOLVED, STATUS_EXTERNAL, STATUS_DYNAMIC,
)


def make_ctx(files):
    from ai_agents.intelligence.parsers.tree_sitter_parser import (
        extract_symbols_structured, extract_calls_structured,
        extract_imports_with_tree_sitter,
    )
    resolver = JavaScriptResolver()
    analyses = {}
    for rel, text in files.items():
        analyses[rel] = {
            'symbols': extract_symbols_structured(rel, text),
            'call_sites': extract_calls_structured(rel, text),
            'imports': extract_imports_with_tree_sitter(rel, text),
            'classes': {}, 'scopes': {}, 'ok': True,
        }
    nodes, symbol_by_id, node_ids = [], {}, set()
    file_symbols, module_files = {}, {}
    for rel, a in analyses.items():
        file_symbols[rel] = a['symbols']
        for sym in a['symbols']:
            sid = sym.get('id') or f"{rel}::{sym.get('qualname','')}"
            sym['id'] = sid
            nodes.append(dict(sym)); symbol_by_id[sid] = sym; node_ids.add(sid)
    graph_ctx = {'nodes': nodes, 'node_ids': node_ids, 'symbol_by_id': symbol_by_id,
                 'module_files': module_files, 'file_symbols': file_symbols,
                 'analyses': analyses, 'class_by_name': {}, 'classes_info': {}, 'subclasses': {}}
    file_ctxs = {rel: resolver.build_context(rel, text, nodes, analyses[rel])
                 for rel, text in files.items()}
    return resolver, graph_ctx, file_ctxs, analyses


def call_for(analysis, name, caller=None):
    for c in analysis['call_sites']:
        if c['name'] == name and (caller is None or c['caller_qualname'] == caller):
            return c
    raise AssertionError(f'call {name} in {caller} not found')


def test_named_import_resolution():
    files = {
        'services.ts': 'export function deleteAccount(id) { return id; }\n',
        'routes.ts': "import { deleteAccount } from './services';\nexport function handler(req) {\n  deleteAccount(req.id);\n}\n",
    }
    r, ctx, fcs, analyses = make_ctx(files)
    call = call_for(analyses['routes.ts'], 'deleteAccount', 'handler')
    res = r.resolve(call, fcs['routes.ts'], ctx)
    assert res.status == STATUS_STATIC_RESOLVED
    assert res.targets == ['services.ts::deleteAccount']


def test_method_call_owner_is_class_qualified():
    """Calls inside a class method must be owned by Class.method, not bare method."""
    files = {'svc.ts': '''class PaymentService {
  validate() { return true; }
  process() { this.validate(); }
}
export { PaymentService };
''' }
    r, ctx, fcs, analyses = make_ctx(files)
    call = call_for(analyses['svc.ts'], 'validate', 'PaymentService.process')
    assert call['call_type'] == 'method'
    res = r.resolve(call, fcs['svc.ts'], ctx)
    assert res.status == STATUS_STATIC_RESOLVED
    assert res.targets == ['svc.ts::PaymentService.validate']


def test_unresolved_receiver_no_fabrication():
    files = {'a.ts': 'export function f(res) {\n  res.sendStatus(204);\n}\n'}
    r, ctx, fcs, analyses = make_ctx(files)
    call = call_for(analyses['a.ts'], 'sendStatus', 'f')
    res = r.resolve(call, fcs['a.ts'], ctx)
    assert res.status == STATUS_UNRESOLVED
    assert res.targets == []


def test_external_import_unresolved_module():
    files = {'a.ts': "import express from 'express';\nexport function f() {\n  express();\n}\n"}
    r, ctx, fcs, analyses = make_ctx(files)
    call = call_for(analyses['a.ts'], 'express', 'f')
    res = r.resolve(call, fcs['a.ts'], ctx)
    assert res.status in (STATUS_EXTERNAL, STATUS_UNRESOLVED)
    assert res.targets == []
