from google.adk.tools import ToolContext


def _emit(tool_context, command):
    commands = list(tool_context.state.get('scene_commands', []))
    commands.append(command)
    tool_context.state['scene_commands'] = commands
    return {'status': 'ok', 'queued': command['type']}


def highlight_vr_path(node_ids: list[str], tool_context: ToolContext, color: str = 'amber') -> dict:
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
    '''Set an edge style: solid for parser-confirmed, dashed for AI-inferred, dotted for ambiguous.'''
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


VALID_MODES = ('REPOS', 'MAP', 'CODE', 'FLOW', 'TESTS', 'IMPACT', 'AGENT')


def set_mode(mode: str, tool_context: ToolContext) -> dict:
    '''Switch the VR workspace to a mode tab. Modes: MAP (graph overview), CODE (source viewer),
    FLOW (control/data flow), TESTS (test results), IMPACT (change impact),
    AGENT (agent activity and proposed diff), REPOS (repository picker).'''
    m = (mode or '').strip().upper()
    if m not in VALID_MODES:
        return {'status': 'error', 'reason': 'Unknown mode %r. Valid modes: %s' % (mode, ', '.join(VALID_MODES))}
    return _emit(tool_context, {'type': 'set_mode', 'mode': m})


def _repo_api():
    from .. import config                                  # imported lazily to avoid import cycles
    from ..intelligence.graph_engine import store
    return config, store


def list_vr_repositories(tool_context: ToolContext) -> dict:
    '''List the repositories the VR workspace can open, and which one is active now.'''
    config, store = _repo_api()
    return {'status': 'ok', 'active': config.REPO_ROOT.name,
            'repositories': [store.info(n) for n in store.list_repos()]}


def open_vr_repository(name: str, tool_context: ToolContext) -> dict:
    '''Open a repository in the VR workspace and make it the active one. Use the exact name from
    list_vr_repositories. Call it once and make no node-level scene changes after it in the same turn.'''
    config, store = _repo_api()
    if tool_context.state.get('pending_approval'):
        return {'status': 'blocked', 'reason': 'A change is waiting for approval. Resolve it before switching repository.'}
    repos = store.list_repos()
    if name not in repos:
        return {'status': 'error', 'reason': 'Unknown repository %r. Available: %s' % (name, ', '.join(repos))}
    try:
        store.activate(name)       # same call /repos/select makes, so the agent's own tools now see this repo
    except Exception as exc:
        return {'status': 'error', 'reason': 'Could not open %s: %s' % (name, exc)}
    result = _emit(tool_context, {'type': 'open_repo', 'repo': name})
    result['active'] = name
    return result


def browse_vr_folder(path: str, tool_context: ToolContext, repo: str = '') -> dict:
    '''Show a folder in the VR repository browser. path is relative to the repository root ('' is the
    root). repo defaults to the active repository. Returns the folder's entries.'''
    config, store = _repo_api()
    name = repo or config.REPO_ROOT.name
    try:
        tree = store.list_tree(name, path or '')
    except KeyError:
        return {'status': 'error', 'reason': 'Unknown repository %r.' % name}
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        return {'status': 'error', 'reason': 'Cannot browse %r: %s' % (path, exc)}
    _emit(tool_context, {'type': 'browse_folder', 'repo': name, 'path': path or ''})
    return {'status': 'ok', 'repo': name, 'path': path or '',
            'entries': [{'name': e['name'], 'type': e['type']} for e in tree['entries'][:60]]}


def open_vr_file(path: str, tool_context: ToolContext, line: int = 1, repo: str = '') -> dict:
    '''Open a file in the VR code viewer, paged to the given line. path is relative to the repository
    root. repo defaults to the active repository.'''
    config, store = _repo_api()
    name = repo or config.REPO_ROOT.name
    try:
        store.read_browser_file(name, path)          # validates the path and that it is a readable text file
    except KeyError:
        return {'status': 'error', 'reason': 'Unknown repository %r.' % name}
    except (FileNotFoundError, ValueError) as exc:
        return {'status': 'error', 'reason': 'Cannot open %r: %s' % (path, exc)}
    return _emit(tool_context, {'type': 'open_file', 'repo': name, 'path': path, 'line': max(1, int(line))})


_DIRECTIONS = {'left': (-1, 0, 0), 'right': (1, 0, 0), 'up': (0, 1, 0), 'down': (0, -1, 0),
               'toward_user': (0, 0, -1), 'away': (0, 0, 1)}

# 'approval' is deliberately absent: the agent must never move, hide or resize the approve/reject panel.
CONTROLLABLE_PANELS = ('status', 'repo', 'code', 'evidence', 'tests', 'activity', 'legend', 'ghost',
                       'impact', 'caption', 'nav')
_ALWAYS_VISIBLE = ('nav', 'status', 'caption')
PANEL_STATES = ('show', 'hide', 'pin', 'unpin', 'minimize', 'restore')


def _clamped_float(value, low: float, high: float):
    try:
        return max(low, min(float(value), high))
    except (TypeError, ValueError):
        return None


def _offset(direction: str, distance: float, limit: float):
    d = _DIRECTIONS.get((direction or '').strip().lower())
    if d is None:
        return None
    dist = _clamped_float(distance, 0.05, limit)
    if dist is None:
        return None
    return [round(c * dist, 3) for c in d]


def _bad_direction(direction):
    return {'status': 'error', 'reason': 'Unknown direction %r. Use: %s' % (direction, ', '.join(_DIRECTIONS))}


def _bad_panel(panel):
    return {'status': 'error', 'reason': 'Unknown or protected panel %r. Use: %s' % (panel, ', '.join(CONTROLLABLE_PANELS))}


def _bad_number(name):
    return {'status': 'error', 'reason': '%s must be a number.' % name}


def move_graph(direction: str, tool_context: ToolContext, distance: float = 0.3) -> dict:
    '''Move the entire graph. direction: left, right, up, down, toward_user or away. distance 0.05 to 2.0.'''
    off = _offset(direction, distance, 2.0)
    if off is None:
        return _bad_direction(direction) if (direction or '').strip().lower() not in _DIRECTIONS else _bad_number('distance')
    return _emit(tool_context, {'type': 'move_graph', 'dx': off[0], 'dy': off[1], 'dz': off[2]})


def zoom_graph(scale: float, tool_context: ToolContext) -> dict:
    '''Set the graph zoom. 1.0 is normal, 0.4 is smallest, 2.2 is largest.'''
    value = _clamped_float(scale, 0.4, 2.2)
    if value is None:
        return _bad_number('scale')
    return _emit(tool_context, {'type': 'zoom_graph', 'value': value})


def move_panel(panel: str, azimuth: float, elevation: float, radius: float, tool_context: ToolContext) -> dict:
    '''Move a panel to a spot on the dome around the user. azimuth in degrees: 0 is straight ahead,
    negative is left (-65 is the usual left wall), positive is right (65 is the usual right wall),
    180 is behind. elevation in degrees: 0 eye level, positive up, negative down. radius in metres,
    1.0 to 3.0 (about 1.8 is typical). Panels: ''' + ', '.join(CONTROLLABLE_PANELS)
    if panel not in CONTROLLABLE_PANELS:
        return _bad_panel(panel)
    az = _clamped_float(azimuth, -180.0, 180.0)
    el = _clamped_float(elevation, -80.0, 80.0)
    radius_value = _clamped_float(radius, 1.0, 3.0)
    if az is None or el is None or radius_value is None:
        return _bad_number('azimuth, elevation and radius')
    return _emit(tool_context, {'type': 'move_panel', 'panel': panel,
                                'azimuth': az, 'elevation': el, 'radius': radius_value})


def scale_panel(panel: str, scale: float, tool_context: ToolContext) -> dict:
    '''Resize a panel. 1.0 is normal, 0.5 smallest, 2.2 largest.'''
    if panel not in CONTROLLABLE_PANELS:
        return _bad_panel(panel)
    value = _clamped_float(scale, 0.5, 2.2)
    if value is None:
        return _bad_number('scale')
    return _emit(tool_context, {'type': 'scale_panel', 'panel': panel, 'value': value})


def set_panel_state(panel: str, state: str, tool_context: ToolContext) -> dict:
    '''Change a panel. state: show (force it visible whatever the tab), hide, pin (lock its position),
    unpin, minimize (title bar only) or restore. nav, status and caption cannot be hidden.'''
    if panel not in CONTROLLABLE_PANELS:
        return _bad_panel(panel)
    if state not in PANEL_STATES:
        return {'status': 'error', 'reason': 'Unknown state %r. Use: %s' % (state, ', '.join(PANEL_STATES))}
    if state == 'hide' and panel in _ALWAYS_VISIBLE:
        return {'status': 'error', 'reason': '%s cannot be hidden.' % panel}
    return _emit(tool_context, {'type': 'panel_state', 'panel': panel, 'state': state})


def highlight_callers(node_id: str, tool_context: ToolContext) -> dict:
    '''Light up the direct callers of a node, like the hold-node menu. Call it alone: it clears
    any highlight set earlier in the same turn.'''
    return _emit(tool_context, {'type': 'highlight_callers', 'node_id': node_id})


def recenter_workspace(tool_context: ToolContext) -> dict:
    '''Bring the whole workspace back in front of the user.'''
    return _emit(tool_context, {'type': 'recenter'})


def reset_layout(tool_context: ToolContext) -> dict:
    '''Undo moves and resizes: panels back to their default spots and size, graph back to default
    position and zoom, workspace recentered. Pinned panels stay where they are.'''
    return _emit(tool_context, {'type': 'reset_layout'})
