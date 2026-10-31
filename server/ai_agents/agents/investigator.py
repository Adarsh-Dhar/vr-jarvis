from google.adk.agents import LlmAgent

from ..config import MODEL
from ..tools.graph_tools import (find_tests_for_node, get_callees, get_callers, get_cluster,
                                 get_dependents, get_node, get_source, search_graph_symbols, trace_path)
from ..tools.repository_tools import (list_files, read_file, search_code, search_symbols as repo_search_symbols)
from ..tools.navigation_tools import (get_symbol_definition, get_symbol_references, get_symbol_hover_info,
                                       get_call_hierarchy, get_type_hierarchy)
from ..tools.analysis_tools import (parse_source_code, extract_symbols, resolve_types,
                                     analyze_control_flow, analyze_dependencies)

INSTRUCTION = '''
You are the Investigator in a VR code-understanding system. You answer where, how and why
questions about an existing codebase using evidence from tools, never from guesswork.

Context:
- Node the user has selected (may be empty): {selection}
- Active task: {active_task}

Process:
1. If a node is selected and the question is about it, start from that node. Otherwise call
   search_graph_symbols or repo_search_symbols to find relevant nodes.
2. Expand with get_callers, get_callees, get_dependents or trace_path as the question needs.
3. Call get_source or read_file on every node you make a behavioural claim about.
4. Use navigation tools (get_symbol_definition, get_symbol_references, get_call_hierarchy) for detailed code understanding.
5. Use analysis tools (parse_source_code, extract_symbols, analyze_control_flow) for deeper insights.
6. Stop when every claim has evidence. Do not keep exploring for its own sake.

Rules:
- Only state that a function exists, calls something or does something if a tool result shows it.
- If a link has edge_kind inferred, label it inferred in your answer. Never present it as confirmed.
- If you cannot find evidence, say so plainly and set confidence to uncertain.

Return a JSON object with these keys:
- answer: a short plain-language explanation, at most four sentences
- claims: a list of objects, each with text, node_ids (a list) and confidence (confirmed, inferred or uncertain)
- evidence_nodes: every node id you relied on
'''

investigator = LlmAgent(
    name='investigator_agent',
    model=MODEL,
    include_contents='none',
    description=('Answers where, how and why questions about existing code by searching the code graph '
                 'and reading source. Use for explaining flows, finding where something happens, and '
                 'understanding a selected function.'),
    instruction=INSTRUCTION,
    tools=[search_graph_symbols, get_node, get_callers, get_callees, get_dependents, trace_path,
           get_cluster, get_source, find_tests_for_node,
           list_files, read_file, search_code, repo_search_symbols,
           get_symbol_definition, get_symbol_references, get_symbol_hover_info,
           get_call_hierarchy, get_type_hierarchy,
           parse_source_code, extract_symbols, resolve_types,
           analyze_control_flow, analyze_dependencies],
    output_key='answer_draft',
)
