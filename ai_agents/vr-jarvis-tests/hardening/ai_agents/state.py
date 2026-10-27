KEYS = [
    'selection',        # node id the user pinched, or empty
    'active_task',      # explain | impact | fix | briefing
    'evidence',         # node ids returned by tools this session
    'changed_nodes',    # change_loader output
    'impact_static',    # static_impact output
    'tests_relevant',   # test_mapper output
    'impact_report',    # impact_synthesizer output
    'answer_draft',     # investigator output
    'proposed_patch',   # patch_agent / patch_repair output
    'test_results',     # verifier output
    'verified_answer',  # critic output
    'briefing',         # briefing_agent output
    'worktree',         # path of the sandbox worktree
    'last_test_run',    # raw test data for read_test_results
    'impact_context',   # last turn's impact report, kept for the patch agent
]

DEFAULT_STATE = {key: '' for key in KEYS}
DEFAULT_STATE.update({
    'evidence': [],
    'scene_commands': [],
    'approved': False,
    'pending_approval': '',
})
