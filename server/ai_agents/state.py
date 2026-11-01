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
    # Phase 1.5: New state keys for agent framework
    'plan',             # Orchestrator's investigation plan
    'findings',         # Append-only list of all findings
    'result_repository',     # Repository Intelligence output
    'result_code_understanding',  # Code Understanding output
    'result_relationship',  # Relationship Intelligence output
    'result_data_flow',     # Data Flow Intelligence output
    'result_runtime',       # Runtime Intelligence output
    'result_debugging',     # Debugging Intelligence output
    'result_security',      # Security and Quality output
    'result_software_eng',  # Software Engineering output
    'result_testing',       # Testing and Verification output
    'result_visualization', # Visualization output
    'result_orchestrator',  # Orchestrator output
    'result_conversational', # Conversational output
    'task_log',         # History of tasks and their status
    'calling_agent',    # Name of agent currently executing (for permission checks)
    # Prompt state keys
    'user_request',     # The user's current request text
    'available_agents', # List of available agent names
    'repo_path',        # Path to the repository root
    'conversation_context',  # Context from previous turns
    'error_context',    # Error context for debugging
    'change_request',   # Requested change description
    'context',          # General context placeholder
]

DEFAULT_STATE = {key: '' for key in KEYS}
DEFAULT_STATE.update({
    'evidence': [],
    'findings': [],
    'scene_commands': [],
    'approved': False,
    'pending_approval': '',
    'task_log': [],
    'user_request': '',
    'available_agents': '',
    'repo_path': '',
    'conversation_context': '',
    'error_context': '',
    'change_request': '',
    'context': '',
})
