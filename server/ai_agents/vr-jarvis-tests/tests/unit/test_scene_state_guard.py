'''Layer 1: scene commands, state handling, permission guard, memory.'''
import json
from unittest import mock

import pytest

from tests.harness.context import FakeCallbackContext, FakeTool, FakeToolContext
from tests.harness.pkg import mod
from tests.harness.schemas import validate_command

st = mod('tools.scene_tools')
ctl = mod('tools.control_tools')
cb = mod('callbacks')
state_mod = mod('state')
memt = mod('tools.memory_tools')

CALLS = [
    (st.highlight_path, (['a', 'b'],), {}),
    (st.highlight_path, (['a'],), {'color': 'red'}),
    (st.dim_unrelated, (['a'],), {}),
    (st.focus_camera, ('a',), {}),
    (st.open_code_panel, ('a',), {}),
    (st.set_edge_style, ('a', 'b', 'dashed'), {}),
    (st.set_edge_style, ('a', 'b', 'solid'), {}),
    (st.show_ghost_diff, ('a', 'diff text'), {}),
    (st.show_test_badges, (['a'], [], ['b']), {}),
    (st.show_approval_prompt, ('Commit?',), {}),
]


@pytest.mark.parametrize('fn,args,kw', CALLS)
def test_every_scene_tool_emits_a_schema_valid_command(fn, args, kw):
    c = FakeToolContext()
    r = fn(*args, c, **kw)
    assert r['status'] == 'ok'
    assert validate_command(c.state['scene_commands'][-1]) == []


def test_scene_tools_reassign_the_list_so_adk_sees_the_change():
    c = FakeToolContext({'scene_commands': []})
    before = c.state['scene_commands']
    st.focus_camera('a', c)
    assert c.state['scene_commands'] is not before and before == []
    st.focus_camera('b', c)
    assert [x['node_id'] for x in c.state['scene_commands']] == ['a', 'b']


def test_schema_validator_catches_bad_commands():
    assert validate_command({'type': 'nope'})
    assert validate_command({'type': 'focus_camera'})
    assert validate_command({'type': 'set_edge_style', 'src': 'a', 'dst': 'b', 'style': 'neon'})
    assert validate_command({'type': 'focus_camera', 'node_id': 'a', 'extra': 1})


def test_init_state_fills_defaults_keeps_existing_and_clears_scene():
    c = FakeCallbackContext({'selection': 'api.login', 'scene_commands': [{'type': 'x'}]})
    cb.init_state(c)
    assert c.state['selection'] == 'api.login'
    assert c.state['scene_commands'] == []
    for key in state_mod.DEFAULT_STATE:
        assert key in c.state
    assert c.state['approved'] is False


def test_default_state_covers_every_declared_key():
    assert set(state_mod.KEYS) <= set(state_mod.DEFAULT_STATE)


@pytest.mark.parametrize('tool', ['commit_changes', 'merge_branch'])
def test_tier2_tools_are_blocked_until_approved(tool):
    c = FakeToolContext({'approved': False})
    r = cb.permission_guard(FakeTool(tool), {}, c)
    assert r and r['status'] == 'blocked'
    c.state['approved'] = True
    assert cb.permission_guard(FakeTool(tool), {}, c) is None


@pytest.mark.parametrize('tool', ['get_source', 'highlight_path', 'create_worktree', 'apply_patch_to_worktree'])
def test_ordinary_tools_are_not_blocked(tool):
    assert cb.permission_guard(FakeTool(tool), {}, FakeToolContext()) is None


def test_live_tests_need_a_worktree(env):
    with mock.patch.object(cb, 'USE_CACHED_TESTS', False):
        assert cb.permission_guard(FakeTool('run_tests'), {}, FakeToolContext())['status'] == 'blocked'
        assert cb.permission_guard(FakeTool('run_tests'), {}, FakeToolContext({'worktree': '/x'})) is None


def test_request_approval_always_resets_approved_and_shows_prompt():
    c = FakeToolContext({'approved': True})
    r = ctl.request_approval('Commit the patch', c)
    assert r['status'] == 'awaiting_user_approval'
    assert c.state['approved'] is False and c.state['pending_approval'] == 'Commit the patch'
    assert c.state['scene_commands'][-1]['type'] == 'show_approval_prompt'


def test_exit_loop_sets_escalate():
    c = FakeToolContext()
    assert c.actions.escalate is False
    ctl.exit_loop(c)
    assert c.actions.escalate is True


def test_memory_roundtrip(env, ctx):
    memt.save_finding('missing ownership check', ['api.deleteAccount'], ctx)
    memt.record_decision('approved patch', ctx)
    m = memt.load_project_memory(ctx)
    assert m['findings'][0]['node_ids'] == ['api.deleteAccount'] and m['decisions'][0]['decision'] == 'approved patch'


def test_corrupt_memory_file_is_an_error_not_a_crash(env, ctx):
    env.memory_path.write_text('{oops')
    try:
        r = memt.load_project_memory(ctx)
    except json.JSONDecodeError:
        pytest.fail('load_project_memory raised JSONDecodeError instead of returning status error')
    assert r['status'] == 'error'
