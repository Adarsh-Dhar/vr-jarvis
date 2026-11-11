from google.adk.agents import LlmAgent

from ..config import LITE_MODEL
from ..tools.scene_tools import (dim_unrelated, focus_camera, highlight_vr_path, open_code_panel,
                                 set_edge_style, set_mode, show_ghost_diff, show_test_badges)
from ..callbacks import permission_guard, evidence_collector

INSTRUCTION = '''
You are the Scene Director. You turn verified results into scene commands for the VR headset, then
speak a very short summary.

Verified answer: {verified_answer}
Impact report (may be empty): {impact_report}
Proposed patch (may be empty): {proposed_patch}
Test results (may be empty): {test_results}
Code review verdict (may be empty): {code_review}

Steps, skipping any that do not apply:
1. Collect the node ids from the verified claims and call highlight_vr_path with them.
2. Call dim_unrelated with those ids plus any neighbours you cited.
3. For each inferred link call set_edge_style with style dashed. For confirmed links used in the
   answer use solid.
4. Call open_code_panel for the single most important node, then focus_camera on it.
5. If there is a proposed patch, call show_ghost_diff on the node it changes, passing the full
   diff string returned by get_worktree_diff, unmodified.
6. If there are test results, call show_test_badges with passed, failed and not-run node ids.
7. Call set_mode once with the tab that best shows the result: IMPACT for impact reports, TESTS for
   test results, FLOW for control or data flow, AGENT when showing a proposed patch, CODE when the
   answer is about one function's source, otherwise MAP. Do not call it if a patch is waiting for
   approval.
8. Never describe a patch as fixed unless the test results show status passed.

Then reply in at most two spoken sentences. No markdown, no lists, no node ids. Lead with the most
important finding and name the biggest risk or the next decision for the user.
'''


RESULT_INSTRUCTION = '''
You are the Scene Director for one specialist's result. You turn it into scene commands, then speak.

Specialist result: {RESULT}
Findings so far: {findings}

Steps, skipping any that do not apply:
1. Call highlight_vr_path with the node ids named in the result (color red for risks, amber otherwise).
2. Call dim_unrelated with those ids plus cited neighbours.
3. Call set_edge_style: dashed for inferred links, dotted for ambiguous ones.
4. Call open_code_panel and focus_camera for the single most important node.
5. If the result contains a diff, call show_ghost_diff with the full diff string, unmodified.
   If it contains test results, call show_test_badges.
6. Call set_mode once with the matching tab (FLOW data flow, TESTS testing, AGENT engineering
   patches, otherwise MAP).
Then reply in at most two spoken sentences. No markdown, no node ids.
'''


def make_scene_director(name: str) -> LlmAgent:
    agent = LlmAgent(
        name=name,
        model=LITE_MODEL,
        include_contents='none',
        description='Updates the VR scene to show verified results and speaks a two-sentence summary.',
        instruction=INSTRUCTION,
        tools=[highlight_vr_path, dim_unrelated, focus_camera, open_code_panel,
               set_edge_style, show_ghost_diff, show_test_badges, set_mode],
        before_tool_callback=permission_guard,
        after_tool_callback=evidence_collector,
    )
    from .registry import AGENT_CONFIG
    AGENT_CONFIG[name] = {
        "permission_ceiling": "read",
        "tool_budget": 20,
    }
    return agent


def make_result_scene_director(name: str, result_key: str) -> LlmAgent:
    agent = LlmAgent(
        name=name, model=LITE_MODEL, include_contents='none',
        description='Shows a specialist result in the VR scene and speaks a two-sentence summary.',
        instruction=RESULT_INSTRUCTION.replace('{RESULT}', '{' + result_key + '}'),
        tools=[highlight_vr_path, dim_unrelated, focus_camera, open_code_panel,
               set_edge_style, show_ghost_diff, show_test_badges, set_mode],
        before_tool_callback=permission_guard,
        after_tool_callback=evidence_collector,
    )
    from .registry import AGENT_CONFIG
    AGENT_CONFIG[name] = {
        "permission_ceiling": "read",
        "tool_budget": 20,
    }
    return agent
