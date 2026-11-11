from types import SimpleNamespace
from typing import List

from google.adk.tools import ToolContext

from ._safe import safe
from .architecture_tools import _put_design
from .design_ops import apply_design_op, finalize_edit, validate_architecture_structure

_DEFAULTS = dict(op='', id='', name='', responsibility='', component_kind='',
                 requirement_ids=[], src='', dst='', kind='', label='')


def _edit(tool_context, op, **fields):
    arch = tool_context.state.get('design')
    if not arch:
        return {'status': 'error', 'error': 'No architecture proposal in this session. Call propose_architecture first.'}
    new_arch, err = apply_design_op(arch, SimpleNamespace(**{**_DEFAULTS, 'op': op, **fields}))
    if err:
        return {'status': 'error', 'error': err}
    had_plan = bool(tool_context.state.get('implementation_plan'))
    new_arch = finalize_edit(arch, new_arch, 'edited_by_agent')
    _put_design(tool_context, design=new_arch, implementation_plan={}, design_compare={}, plan_stale=had_plan)
    return {'status': 'ok', 'revision': new_arch['revision'], 'architecture': new_arch}


@safe
def add_component(name: str, responsibility: str, component_kind: str, tool_context: ToolContext,
                  requirement_ids: List[str] = None) -> dict:
    return _edit(tool_context, 'add_component', name=name, responsibility=responsibility,
                 component_kind=component_kind, requirement_ids=requirement_ids or [])


@safe
def remove_component(component_id: str, tool_context: ToolContext) -> dict:
    return _edit(tool_context, 'remove_component', id=component_id)


@safe
def update_component(component_id: str, tool_context: ToolContext, name: str = '',
                     responsibility: str = '', component_kind: str = '') -> dict:
    return _edit(tool_context, 'update_component', id=component_id, name=name,
                 responsibility=responsibility, component_kind=component_kind)


@safe
def add_relationship(src: str, dst: str, kind: str, tool_context: ToolContext, label: str = '') -> dict:
    return _edit(tool_context, 'add_relationship', src=src, dst=dst, kind=kind, label=label)


@safe
def remove_relationship(relationship_id: str, tool_context: ToolContext) -> dict:
    return _edit(tool_context, 'remove_relationship', id=relationship_id)


@safe
def update_relationship(relationship_id: str, tool_context: ToolContext, kind: str = '', label: str = '') -> dict:
    return _edit(tool_context, 'update_relationship', id=relationship_id, kind=kind, label=label)


@safe
def get_proposed_architecture(tool_context: ToolContext) -> dict:
    arch = tool_context.state.get('design')
    if not arch:
        return {'status': 'not_found', 'error': 'No architecture proposal in this session.'}
    return {'status': 'ok', 'architecture': arch}


@safe
def validate_architecture(tool_context: ToolContext) -> dict:
    arch = tool_context.state.get('design')
    if not arch:
        return {'status': 'not_found', 'error': 'No architecture proposal in this session.'}
    problems = validate_architecture_structure(arch)
    return {'status': 'ok' if not problems else 'invalid', 'problems': problems}
