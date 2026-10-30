from google.adk.tools import ToolContext


def _emit(tool_context, command):
    commands = list(tool_context.state.get('scene_commands', []))
    commands.append(command)
    tool_context.state['scene_commands'] = commands
    return {'status': 'ok', 'queued': command['type']}


def highlight_path(node_ids: list[str], tool_context: ToolContext, color: str = 'amber') -> dict:
    '''Light up these nodes and the edges between them in the VR scene.'''
    return _emit(tool_context, {'type': 'highlight_path', 'node_ids': node_ids, 'color': color})


def dim_unrelated(keep_ids: list[str], tool_context: ToolContext) -> dict:
    '''Fade every node not in keep_ids into the background.'''
    return _emit(tool_context, {'type': 'dim_unrelated', 'keep_ids': keep_ids})


def focus_camera(node_id: str, tool_context: ToolContext) -> dict:
    '''Move the user's view toward this node.'''
    return _emit(tool_context, {'type': 'focus_camera', 'node_id': node_id})


def open_code_panel(node_id: str, tool_context: ToolContext) -> dict:
    '''Open a readable source panel in front of the user for this node.'''
    return _emit(tool_context, {'type': 'open_code_panel', 'node_id': node_id})


def set_edge_style(src: str, dst: str, style: str, tool_context: ToolContext) -> dict:
    '''Set an edge style: solid for parser-confirmed, dashed for AI-inferred, runtime for observed.'''
    return _emit(tool_context, {'type': 'set_edge_style', 'src': src, 'dst': dst, 'style': style})


def show_ghost_diff(node_id: str, diff: str, tool_context: ToolContext) -> dict:
    '''Show a proposed change as a translucent ghost node attached to node_id. Nothing is applied.'''
    return _emit(tool_context, {'type': 'show_ghost_diff', 'node_id': node_id, 'diff': diff})


def show_test_badges(passed_ids: list[str], failed_ids: list[str], not_run_ids: list[str],
                     tool_context: ToolContext) -> dict:
    '''Attach pass, fail and not-run badges to nodes.'''
    return _emit(tool_context, {'type': 'show_test_badges', 'passed': passed_ids,
                                'failed': failed_ids, 'not_run': not_run_ids})


def show_approval_prompt(summary: str, tool_context: ToolContext) -> dict:
    '''Show an approve or reject panel the user answers with a pinch.'''
    return _emit(tool_context, {'type': 'show_approval_prompt', 'summary': summary})
