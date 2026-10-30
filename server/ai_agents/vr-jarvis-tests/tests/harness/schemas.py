'''Contract between the agents and the Unity client: every scene command type and its required fields.'''
SCENE_SCHEMA = {
    'highlight_path': {'node_ids': list, 'color': str},
    'dim_unrelated': {'keep_ids': list},
    'focus_camera': {'node_id': str},
    'open_code_panel': {'node_id': str},
    'set_edge_style': {'src': str, 'dst': str, 'style': str},
    'show_ghost_diff': {'node_id': str, 'diff': str},
    'show_test_badges': {'passed': list, 'failed': list, 'not_run': list},
    'show_approval_prompt': {'summary': str},
}
EDGE_STYLES = {'solid', 'dashed', 'runtime'}


def validate_command(cmd):
    '''Return a list of problems with one scene command (empty list means valid).'''
    if not isinstance(cmd, dict) or 'type' not in cmd:
        return ['not a command object']
    spec = SCENE_SCHEMA.get(cmd['type'])
    if spec is None:
        return ['unknown command type: %s' % cmd['type']]
    problems = []
    for key, typ in spec.items():
        if key not in cmd:
            problems.append('%s missing %s' % (cmd['type'], key))
        elif not isinstance(cmd[key], typ):
            problems.append('%s.%s should be %s' % (cmd['type'], key, typ.__name__))
    extra = set(cmd) - set(spec) - {'type'}
    if extra:
        problems.append('%s has unexpected fields %s' % (cmd['type'], sorted(extra)))
    if cmd['type'] == 'set_edge_style' and cmd.get('style') not in EDGE_STYLES:
        problems.append('bad edge style %r' % cmd.get('style'))
    return problems


def node_ids_in(cmd):
    ids = []
    for key in ('node_ids', 'keep_ids', 'passed', 'failed', 'not_run'):
        if isinstance(cmd.get(key), list):
            ids += cmd[key]
    for key in ('node_id', 'src', 'dst'):
        if isinstance(cmd.get(key), str):
            ids.append(cmd[key])
    return ids
