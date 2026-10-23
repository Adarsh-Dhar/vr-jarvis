from google.adk.agents import LlmAgent

from ..config import MODEL
from ..tools.git_tools import get_diff, list_changed_nodes
from ..tools.graph_tools import (find_tests_for_node, get_callers, get_coverage, get_dependents,
                                 get_node, trace_path)

change_loader = LlmAgent(
    name='change_loader_agent',
    model=MODEL,
    description='Loads the change under review, or the selected node as a hypothetical change.',
    instruction='''
Load the change to analyse.
1. Call list_changed_nodes and get_diff.
2. If the user's request is about changing, removing or editing the selected node ({selection})
   rather than reviewing the diff, use the selected node as the changed node instead.
3. Call get_node on each changed node to confirm it exists.
Return a JSON object with keys: source (diff or selection), branch, changed_nodes (list of node ids),
diff_summary (at most two sentences).
''',
    tools=[list_changed_nodes, get_diff, get_node],
    output_key='changed_nodes',
)

static_impact = LlmAgent(
    name='static_impact_agent',
    model=MODEL,
    description='Finds everything that depends on the changed nodes using the code graph.',
    instruction='''
Changed nodes: {changed_nodes}

For each changed node call get_dependents with max_depth 4 and get_callers with depth 2.
Split what you find into two groups:
- confirmed: every hop on the chain has edge_kind confirmed
- unresolved: at least one hop has edge_kind inferred
Use trace_path to show the chain for the three most important dependents.
Add nothing that no tool returned.
Return a JSON object with keys: confirmed (list of objects with id, depth, via),
unresolved (same, plus reason), counts (confirmed and unresolved totals).
''',
    tools=[get_dependents, get_callers, trace_path, get_node],
    output_key='impact_static',
)

test_mapper = LlmAgent(
    name='test_mapper_agent',
    model=MODEL,
    description='Finds which tests cover the changed nodes and their callers, and which paths are untested.',
    instruction='''
Changed nodes: {changed_nodes}

For each changed node and each of its callers up to 2 hops away (use get_callers), call
find_tests_for_node and get_coverage.
Return a JSON object with keys: tests (list of test ids with file), untested_nodes (node ids with no
tests), low_coverage_nodes (node ids with coverage below 0.5).
''',
    tools=[get_callers, find_tests_for_node, get_coverage],
    output_key='tests_relevant',
)

impact_synthesizer = LlmAgent(
    name='impact_synthesizer_agent',
    model=MODEL,
    description='Merges static impact and test mapping into one ranked impact report.',
    instruction='''
Merge these inputs into one impact report.
Changed nodes: {changed_nodes}
Static impact: {impact_static}
Relevant tests: {tests_relevant}

Rules:
- Only mention node ids that appear in the inputs above.
- Keep confirmed and unresolved links separate. If you add a link that is not in the inputs, mark its
  edge_kind as inferred and give a one-sentence reason.
- Rank each affected node by risk: higher when it is untested, low coverage, or reached by a long chain.

Return a JSON object with keys: summary (at most three sentences), risk_level (low, medium or high),
affected (list of objects with id, risk, edge_kind, reason, untested), inferred_links (list of src, dst,
reason), recommended_tests (list), claims (list of objects with text, node_ids, confidence).
''',
    output_key='impact_report',
)
