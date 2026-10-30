from google.adk.agents import LlmAgent

from ..callbacks import permission_guard
from ..config import MODEL
from ..tools.control_tools import exit_loop
from ..tools.exec_tools import read_test_results, run_tests, run_typecheck
from ..tools.git_tools import apply_patch_to_worktree, create_worktree, get_worktree_diff
from ..tools.graph_tools import find_tests_for_node, get_callers, get_source, search_symbols
from ..tools.repository_tools import (list_files, read_file, search_code, search_symbols as repo_search_symbols)
from ..tools.navigation_tools import (get_symbol_definition, get_symbol_references, get_symbol_hover_info,
                                       get_call_hierarchy)

patch_agent = LlmAgent(
    name='patch_agent',
    model=MODEL,
    include_contents='none',
    description='Proposes a minimal code change with a test, applied only inside a sandbox worktree.',
    instruction='''
You write a small, safe patch for the user's request.
Selected node (may be empty): {selection}
Impact context from the last impact analysis (may be empty): {impact_context}

Process:
1. Locate the code to change with search_symbols, repo_search_symbols or the selected node.
2. Read it and its neighbours with get_source, read_file and get_callers so you follow the repo's conventions.
3. Use navigation tools (get_symbol_definition, get_symbol_references) to understand the code structure.
4. Call create_worktree, then write a minimal unified diff that includes a regression test, and
   apply it with apply_patch_to_worktree. If applying fails, fix the diff and retry once.
5. Call get_worktree_diff to get the diff that was actually applied.

Rules:
- Touch only what the request needs. Never commit or merge.
- State any assumption you made.

Return a JSON object with keys: summary, files (list of paths), diff (from get_worktree_diff),
tests_added (list of test file paths), assumptions (list), claims (list of objects with text, node_ids,
confidence).
''',
    tools=[search_symbols, get_source, get_callers, find_tests_for_node,
           create_worktree, apply_patch_to_worktree, get_worktree_diff,
           list_files, read_file, search_code, repo_search_symbols,
           get_symbol_definition, get_symbol_references, get_symbol_hover_info,
           get_call_hierarchy],
    before_tool_callback=permission_guard,
    output_key='proposed_patch',
)

verifier = LlmAgent(
    name='verifier_agent',
    model=MODEL,
    include_contents='none',
    description='Runs the relevant tests and type check on the sandbox patch and reports exact results.',
    instruction='''
Patch under test: {proposed_patch}
Tests already known to be relevant: {tests_relevant}

Process:
1. Call run_tests with the test files from the patch plus the relevant tests above.
2. Call run_typecheck.
3. If tests passed and the type check passed, call exit_loop.

Rules:
- Report exactly what the tools returned. Never say passed unless a tool result says passed.
- If a tool errors or a test did not run, list it as not_run.

Return a JSON object with keys: status (passed, failed or not_run), passed (list), failed (list of
objects with id and message), not_run (list), typecheck (passed, failed or not_run).
''',
    tools=[run_tests, run_typecheck, read_test_results, exit_loop],
    before_tool_callback=permission_guard,
    output_key='test_results',
)

patch_repair = LlmAgent(
    name='patch_repair_agent',
    model=MODEL,
    include_contents='none',
    description='Repairs a failing patch using the test failure output.',
    instruction='''
The tests did not all pass. Repair the patch.
Current patch: {proposed_patch}
Latest test results: {test_results}

Process:
1. Read the failure messages. Call get_source on the node involved.
2. Write an incremental unified diff that fixes the failure. The earlier patch is already applied in
   the worktree. Apply it with apply_patch_to_worktree.
3. Call get_worktree_diff to get the full diff that is now in place.

Return a JSON object in the same shape as the current patch (summary, files, diff, tests_added,
assumptions, claims), with diff taken from get_worktree_diff and summary updated.
''',
    tools=[get_source, apply_patch_to_worktree, get_worktree_diff],
    before_tool_callback=permission_guard,
    output_key='proposed_patch',
)
