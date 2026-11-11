"""Bind a recorded call_shape to a callee's formal parameters.

The expression evaluator records, for every ``Call`` operation, a structured
``call_shape`` (positional arguments, keyword arguments, starred flags and the
use/operation ids each argument contributes). This module maps those arguments
onto the callee's ``ast.arguments`` so cross-function data-flow edges name a
real parameter instead of guessing from argument position alone.

Rules:
- Positional arguments bind by position; keyword arguments bind by name.
- ``self``/``cls`` of a method are bound to the receiver, never to an argument.
- Parameters with defaults that receive no argument are reported as defaults,
  not as flows.
- ``*args``/``**kwargs`` absorb surplus arguments when present.
- Anything that cannot be bound statically (starred expansion, unknown
  keyword without ``**kwargs``, argument/parameter conflicts) comes back
  unresolved — never guessed.
"""
import ast
from typing import Any, Dict, List, Optional


def _positional_params(func_ast) -> List[Dict[str, Any]]:
    args = func_ast.args
    params = []
    for a in list(getattr(args, 'posonlyargs', []) or []) + list(args.args or []):
        params.append({'name': a.arg, 'kind': 'positional', 'has_default': False})
    # defaults align to the tail of (posonlyargs + args)
    defaults = list(getattr(args, 'defaults', []) or [])
    if defaults:
        for p, _ in zip(params[-len(defaults):], defaults):
            p['has_default'] = True
    return params


def _keyword_params(func_ast) -> List[Dict[str, Any]]:
    params = []
    for a in getattr(func_ast.args, 'kwonlyargs', []) or []:
        params.append({'name': a.arg, 'kind': 'keyword', 'has_default': False})
    kw_defaults = getattr(func_ast.args, 'kw_defaults', []) or []
    for p, d in zip(params, kw_defaults):
        if d is not None:
            p['has_default'] = True
    return params


def formal_parameters(func_ast, is_method: bool = False) -> Dict[str, Any]:
    """Ordered formal parameter description for a function AST.

    Returns {'positional': [...], 'vararg': name|None, 'keywords': [...],
    'kwarg': name|None, 'all': [names in signature order]}.
    When ``is_method`` is true the leading ``self``/``cls`` parameter is
    excluded — it binds to the receiver, not to a call argument.
    """
    if not isinstance(func_ast, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return {'positional': [], 'vararg': None, 'keywords': [],
                'kwarg': None, 'all': []}
    args = func_ast.args
    positional = _positional_params(func_ast)
    if is_method and positional and positional[0]['name'] in ('self', 'cls'):
        positional = positional[1:]
    keywords = _keyword_params(func_ast)
    vararg = args.vararg.arg if getattr(args, 'vararg', None) else None
    kwarg = args.kwarg.arg if getattr(args, 'kwarg', None) else None
    all_names = [p['name'] for p in positional] + ([vararg] if vararg else []) \
        + [p['name'] for p in keywords] + ([kwarg] if kwarg else [])
    return {'positional': positional, 'vararg': vararg,
            'keywords': keywords, 'kwarg': kwarg, 'all': all_names}


def bind_call(call_shape: Optional[Dict[str, Any]], func_ast,
              is_method: bool = False) -> Dict[str, Any]:
    """Bind a recorded call_shape to the callee's formal parameters.

    Returns::

        {'status': 'ok'|'partial'|'unresolved',
         'bindings': [{'param': name, 'param_kind': ..., 'arg_index': i|None,
                       'keyword': name|None, 'use_ids': [...],
                       'operation_id': ...|None, 'status': 'bound'|'unresolved'}],
         'unbound_arguments': [{'position': i} | {'keyword': name}],
         'defaults': [param names supplied by default],
         'reason': str|None}

    ``status`` is 'ok' when every supplied argument bound, 'partial' when some
    did, 'unresolved' when none did or no signature was available.
    """
    if not isinstance(call_shape, dict):
        return {'status': 'unresolved', 'bindings': [], 'unbound_arguments': [],
                'defaults': [], 'reason': 'no call_shape recorded'}
    if not isinstance(func_ast, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return {'status': 'unresolved', 'bindings': [], 'unbound_arguments': [],
                'defaults': [], 'reason': 'callee signature unavailable'}

    params = formal_parameters(func_ast, is_method=is_method)
    positional = list(params['positional'])
    keywords = {p['name']: p for p in params['keywords']}
    # positional-or-keyword params can also be filled by name
    for p in positional:
        keywords.setdefault(p['name'], p)

    bindings: List[Dict[str, Any]] = []
    unbound: List[Dict[str, Any]] = []
    filled: set = set()
    positional_cursor = 0
    star_seen = False

    def _bind(param_name, param_kind, arg, arg_index=None, keyword=None):
        bindings.append({
            'param': param_name,
            'param_kind': param_kind,
            'arg_index': arg_index,
            'keyword': keyword,
            'use_ids': list(arg.get('use_ids') or []),
            'operation_id': arg.get('operation_id'),
            'status': 'bound',
        })
        filled.add(param_name)

    def _unresolved_arg(arg, arg_index=None, keyword=None):
        bindings.append({
            'param': None,
            'param_kind': None,
            'arg_index': arg_index,
            'keyword': keyword,
            'use_ids': list(arg.get('use_ids') or []),
            'operation_id': arg.get('operation_id'),
            'status': 'unresolved',
        })
        unbound.append({'position': arg_index} if arg_index is not None
                       else {'keyword': keyword})

    for i, arg in enumerate(call_shape.get('positional') or []):
        if star_seen:
            # A starred expansion makes every later position ambiguous.
            _unresolved_arg(arg, arg_index=i)
            continue
        if arg.get('starred'):
            star_seen = True
            if params['vararg']:
                _bind(params['vararg'], 'vararg', arg, arg_index=i)
            else:
                _unresolved_arg(arg, arg_index=i)
            continue
        if positional_cursor < len(positional) \
                and positional[positional_cursor]['name'] not in filled:
            p = positional[positional_cursor]
            _bind(p['name'], 'positional', arg, arg_index=i)
            positional_cursor += 1
        elif params['vararg']:
            _bind(params['vararg'], 'vararg', arg, arg_index=i)
        else:
            _unresolved_arg(arg, arg_index=i)

    for arg in call_shape.get('keywords') or []:
        if arg.get('starred') or arg.get('name') is None:
            # **kwargs expansion
            if params['kwarg']:
                _bind(params['kwarg'], 'kwarg', arg, keyword=None)
            else:
                _unresolved_arg(arg, keyword=None)
            continue
        name = arg.get('name')
        p = keywords.get(name)
        if p is None:
            if params['kwarg']:
                _bind(params['kwarg'], 'kwarg', arg, keyword=name)
            else:
                _unresolved_arg(arg, keyword=name)
            continue
        if p['name'] in filled:
            _unresolved_arg(arg, keyword=name)  # positional/keyword conflict
            continue
        _bind(p['name'], 'keyword', arg, keyword=name)

    supplied = {b['param'] for b in bindings if b['param']}
    defaults = [p['name'] for p in positional + params['keywords']
                if p['name'] not in supplied and p.get('has_default')]
    missing = [p['name'] for p in positional + params['keywords']
               if p['name'] not in supplied and not p.get('has_default')
               and p['name'] not in (params['vararg'], params['kwarg'])]

    bound = sum(1 for b in bindings if b['status'] == 'bound')
    total = len(call_shape.get('positional') or []) + len(call_shape.get('keywords') or [])
    if not bindings:
        status = 'ok' if total == 0 else 'unresolved'
    elif bound == total:
        status = 'ok'
    elif bound:
        status = 'partial'
    else:
        status = 'unresolved'

    out = {'status': status, 'bindings': bindings, 'unbound_arguments': unbound,
           'defaults': defaults, 'missing_parameters': missing, 'reason': None}
    if status == 'unresolved' and not bindings:
        out['reason'] = 'no arguments could be bound to the callee signature'
    return out
