from google.adk.agents import LlmAgent

from ..config import MODEL
from ..tools.git_tools import get_branch_info, list_changed_nodes
from ..tools.graph_tools import find_tests_for_node, get_callers, get_coverage
from ..tools.memory_tools import load_project_memory
from ..callbacks import permission_guard, evidence_collector

briefing_agent = LlmAgent(
    name='briefing_agent',
    model=MODEL,
    include_contents='none',
    description='Prepares the opening briefing for a project: what changed, what is risky, what is untested.',
    instruction='''
Prepare a short opening briefing.
1. Call load_project_memory for earlier findings and unfinished work.
2. Call get_branch_info and list_changed_nodes.
3. For each changed node call get_callers with depth 2, find_tests_for_node and get_coverage.

Return a JSON object with keys: summary (at most three sentences covering what changed, what is
risky and what is untested), risky_nodes (list of node ids), unfinished_work (list from memory),
claims (list of objects with text, node_ids, confidence).
''',
    tools=[load_project_memory, get_branch_info, list_changed_nodes, get_callers,
           find_tests_for_node, get_coverage],
    output_key='briefing',
    before_tool_callback=permission_guard,
    after_tool_callback=evidence_collector,
)
from .registry import AGENT_CONFIG
AGENT_CONFIG['briefing_agent'] = {
    "permission_ceiling": "read",
    "tool_budget": 20,
}
