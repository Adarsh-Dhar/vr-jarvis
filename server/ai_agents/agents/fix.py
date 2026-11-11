from google.adk.agents import LlmAgent

from ..callbacks import permission_guard, evidence_collector
from ..config import MODEL
from ..tools.control_tools import exit_loop
from ..tools.exec_tools import read_test_results, run_tests, run_typecheck
from ..tools.git_tools import (apply_patch_to_worktree, create_worktree, get_worktree_diff,
                               read_worktree_file)
from ..tools.graph_tools import find_tests_for_node, get_callers, get_source, search_graph_symbols
from ..tools.repository_tools import (list_files, read_file, read_file_range, search_code,
                                      search_symbols as repo_search_symbols)
from ..tools.software_engineering_tools import record_task_targets
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
Active plan task (empty unless the request came from WORK ON IT): {active_task}

When active_task is not empty it is the authoritative task record (id, title, description,
files, symbols, acceptance_criteria, depends_on). Its files and symbols are SUGGESTIONS only.

Process:
1. If active_task is present: read EVERY file in active_task.files with read_file, and look up every
   entry in active_task.symbols with get_source or search_graph_symbols, BEFORE writing any diff.
2. Otherwise locate the code to change with search_graph_symbols, repo_search_symbols or the selected node.
3. Read neighbours with get_source, read_file and get_callers so you follow the repo's conventions.
4. Use navigation tools (get_symbol_definition, get_symbol_references) to understand the code structure.
5. If active_task is present, call record_task_targets ONCE, before editing, with confirmed_targets
   (files you will really modify) and rejected_targets (suggested files you will not touch, each
   {file, reason}). Do not edit a file that is not in confirmed_targets.
6. Call create_worktree, then write a minimal unified diff that includes a regression test, and
   apply it with apply_patch_to_worktree. If applying fails, fix the diff and retry once.
7. Call get_worktree_diff to get the diff that was actually applied.

Rules:
- Touch only what the request needs. Never commit or merge.
- If active_task is present, the patch must satisfy every item in active_task.acceptance_criteria;
  the regression test must exercise them. List each criterion and how it is met in assumptions.
- State any assumption you made.

Return a JSON object with keys: summary, files (list of paths), diff (from get_worktree_diff),
tests_added (list of test file paths), assumptions (list), claims (list of objects with text, node_ids,
confidence).
''',
    tools=[search_graph_symbols, get_source, get_callers, find_tests_for_node,
           record_task_targets, create_worktree, apply_patch_to_worktree, get_worktree_diff,
           list_files, read_file, search_code, repo_search_symbols,
           get_symbol_definition, get_symbol_references, get_symbol_hover_info,
           get_call_hierarchy],
    before_tool_callback=permission_guard,
    after_tool_callback=evidence_collector,
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
    after_tool_callback=evidence_collector,
    output_key='test_results',
)

code_reviewer = LlmAgent(
    name='code_reviewer',
    model=MODEL,
    include_contents='none',
    description='Independently reviews the proposed diff for logic, error handling and acceptance criteria before commit.',
    instruction='''
You are the independent Code Reviewer. You review the patch that is about to be committed.
This review is separate from test execution: passing tests do not excuse logic or
error-handling defects, and test results are context, not your verdict.

Patch under review: {proposed_patch}
Test results (context only): {test_results}
Active plan task (may be empty): {active_task}

Process:
1. Call get_worktree_diff to see the exact diff that will be committed.
2. For every changed file call read_worktree_file to see the post-patch content in
   context; use read_file, read_file_range, search_code or get_source for unchanged
   surrounding code and callers.
3. Inspect the diff for: incorrect or risky logic, missing error handling on new
   failure paths, swallowed exceptions, debug leftovers, unrelated or accidental
   changes, and missing regression tests for the new behaviour.
4. If active_task is present, check every item in active_task.acceptance_criteria
   against the diff and report each as met, not_met or unknown.
5. If changed behaviour lacks test coverage, list concrete test cases to add.

Rules:
- You only review. Never modify files, never run tests, never commit.
- verdict is 'approve' only when you find no blocking issue; use 'changes_requested'
  when any blocker or unmet acceptance criterion exists.
- Cite file and approximate line for every finding.

Return a JSON object with keys: verdict (approve|changes_requested), summary,
findings (list of {severity: blocker|warning|info, file, line, issue, suggestion}),
acceptance (list of {criterion, status: met|not_met|unknown, note}),
suggested_tests (list of strings).
''',
    tools=[get_worktree_diff, read_worktree_file, read_file, read_file_range,
           search_code, get_source, find_tests_for_node],
    before_tool_callback=permission_guard,
    after_tool_callback=evidence_collector,
    output_key='code_review',
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
    after_tool_callback=evidence_collector,
    output_key='proposed_patch',
)
