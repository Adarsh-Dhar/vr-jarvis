#!/usr/bin/env python3
"""
Generate Layer 1-2 tests for Priority 2 tools
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from test_spec_generator import TestSpecGenerator

# Priority 2 tools (52 tools)
PRIORITY_2_TOOLS = [
    # API Database Toolkit (26)
    'inspect_api_schema', 'analyze_api_contract', 'trace_api_call', 'analyze_api_security',
    'inspect_http_routes', 'inspect_middleware', 'inspect_authentication', 'inspect_authorization',
    'discover_database_schema', 'inspect_database_connection', 'analyze_database_queries',
    'trace_database_operation', 'analyze_database_performance', 'inspect_database_schema',
    'inspect_tables', 'inspect_columns', 'inspect_indexes', 'inspect_foreign_keys',
    'inspect_sql_queries', 'explain_query_plan', 'inspect_orm_models', 'inspect_orm_relationships',
    'trace_transaction', 'trace_migrations', 'map_api_to_database', 'visualize_database_schema',

    # Documentation Toolkit (18)
    'search_documentation', 'generate_code_documentation', 'extract_docstrings',
    'verify_documentation_coverage', 'read_documentation', 'search_external_docs',
    'search_library_docs', 'search_framework_docs', 'search_api_docs', 'search_issues',
    'search_prs', 'search_discussions', 'generate_architecture_doc',
    'generate_function_documentation', 'generate_dependency_documentation',
    'generate_investigation_report', 'update_knowledge', 'retrieve_knowledge',

    # Git History Toolkit (1)
    'trace_file_history',

    # Git Tools (7)
    'get_diff', 'list_changed_nodes', 'get_branch_info', 'create_worktree',
    'apply_patch_to_worktree', 'get_worktree_diff', 'commit_worktree',
]

def main():
    test_root = Path(__file__).parent.parent
    generator = TestSpecGenerator(test_root)
    generator.load_all_tool_signatures()

    # Generate Layer 1 tests (T01-T09) for all Priority 2 tools
    test_types_layer1 = [f'T0{i}' for i in range(1, 10)]

    total_specs = 0
    failed_tools = []

    print("Generating Layer 1 tests (T01-T09) for Priority 2 tools...")
    for tool_name in PRIORITY_2_TOOLS:
        print(f"  {tool_name}...")

        try:
            specs = generator.generate_for_tool(tool_name, test_types_layer1)
            saved = generator.save_specs(specs, test_root / 'tests')
            total_specs += len(saved)
        except Exception as e:
            import traceback
            print(f"    ERROR: {e}")
            failed_tools.append(tool_name)

    print(f"\nLayer 1 specs generated: {total_specs}")

    # Generate Layer 2 tests (T10-T15) for all Priority 2 tools
    test_types_layer2 = [f'T1{i}' for i in range(0, 6)]

    total_specs_layer2 = 0

    print("\nGenerating Layer 2 tests (T10-T15) for Priority 2 tools...")
    for tool_name in PRIORITY_2_TOOLS:
        print(f"  {tool_name}...")

        try:
            specs = generator.generate_for_tool(tool_name, test_types_layer2)
            saved = generator.save_specs(specs, test_root / 'tests')
            total_specs_layer2 += len(saved)
        except Exception as e:
            import traceback
            print(f"    ERROR: {e}")
            if tool_name not in failed_tools:
                failed_tools.append(tool_name)

    print(f"\nLayer 2 specs generated: {total_specs_layer2}")

    total_specs += total_specs_layer2

    print(f"\n{'='*60}")
    print(f"Total specs generated: {total_specs}")
    print(f"Failed tools: {len(failed_tools)}")

    if failed_tools:
        print("\nFailed tools:")
        for tool in failed_tools:
            print(f"  - {tool}")

    print(f"\nOutput directory: {test_root / 'tests'}")


if __name__ == '__main__':
    main()
