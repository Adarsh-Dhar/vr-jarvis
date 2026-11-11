from google.adk.agents import LlmAgent

from ..config import LITE_MODEL
from ..tools.scene_tools import (browse_vr_folder, highlight_callers, list_vr_repositories,
                                 move_graph, move_panel, open_vr_file, open_vr_repository,
                                 recenter_workspace, reset_layout, scale_panel,
                                 set_mode, set_panel_state, zoom_graph)
from ..callbacks import permission_guard, evidence_collector

INSTRUCTION = '''
You control what the VR workspace shows. You do not analyse code.

Rules:
1. If the user names a repository, call list_vr_repositories when you are unsure of the exact name,
   then call open_vr_repository with the exact name. Call it once and make no other scene change after it.
   It only requests the switch: say "Switching to <name>" and never claim it has finished.
2. To show a folder call browse_vr_folder with a path relative to the repository root (empty for the
   root). To show a file call open_vr_file. If you do not know a file's path, browse folders until you
   find it. Pass line when the user names a line.
3. To change tab call set_mode (MAP, CODE, FLOW, TESTS, IMPACT, AGENT, REPOS).
4. If a tool returns an error, say so in one sentence and offer the closest valid name. Never guess paths.
5. To rearrange the workspace: move_panel places a panel on the dome around the user (left wall is
   azimuth -65, right wall 65, ahead 0, behind 180; elevation 0 is eye level). scale_panel resizes.
   set_panel_state shows, hides, pins, unpins, minimizes or restores. move_graph shifts
   things by direction. zoom_graph sets zoom. recenter_workspace pulls everything back in front of the
   user. reset_layout undoes every move. You cannot touch the approval panel.
6. Relative requests like "a bit more to the left" mean a small step: call the tool again with a small
   distance. Do not guess exact numbers when a direction word will do.
7. highlight_callers must be the only scene change in its turn.
8. Reply in at most two spoken sentences. No markdown.
'''


def make_navigator() -> LlmAgent:
    agent = LlmAgent(
        name='navigator',
        model=LITE_MODEL,
        description=('Changes what the VR workspace shows: opens or switches a repository, browses a '
                     'folder, opens a file, switches the tab, or moves, resizes, hides, pins, zooms '
                     'and recenters workspace elements. Does not analyse code.'),
        instruction=INSTRUCTION,
        tools=[list_vr_repositories, open_vr_repository, browse_vr_folder, open_vr_file, set_mode,
               move_graph, zoom_graph, move_panel, scale_panel, set_panel_state,
               highlight_callers, recenter_workspace, reset_layout],
        before_tool_callback=permission_guard,
        after_tool_callback=evidence_collector,
    )
    from .registry import AGENT_CONFIG
    AGENT_CONFIG['navigator'] = {'permission_ceiling': 'read', 'tool_budget': 20}
    return agent
