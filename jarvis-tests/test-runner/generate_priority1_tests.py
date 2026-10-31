#!/usr/bin/env python3
"""
Generate Layer 1 tests for all Priority 1 tools
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from test_spec_generator import TestSpecGenerator

# Priority 1 tools (66 tools)
PRIORITY_1_TOOLS = [
    # Analysis Tools (11)
    'resolve_types', 'resolve_references', 'analyze_data_flow', 'analyze_dependencies',
    'analyze_code_complexity', 'detect_code_duplication', 'detect_dead_code',
    'analyze_exceptions', 'analyze_annotations', 'analyze_macros', 'analyze_generated_code',

    # Data Flow Intelligence Tools (18)
    'trace_variable_origin', 'trace_variable_usage', 'trace_variable_modifications',
    'trace_parameter_flow', 'trace_return_value_flow', 'trace_transformations',
    'trace_cross_function_flow', 'trace_cross_service_flow', 'trace_database_reads',
    'trace_database_writes', 'trace_api_data_flow', 'trace_file_operations',
    'trace_state_changes', 'build_data_flow_graph', 'identify_data_leaks',
    'identify_data_sinks', 'identify_data_sources', 'identify_validation_gaps',

    # Relationship Intelligence Tools (11)
    'trace_call_chain', 'find_indirect_callers', 'find_downstream_dependencies',
    'find_shared_dependencies', 'build_reference_graph', 'build_class_relationship_graph',
    'find_interface_implementations', 'trace_cross_module_relationships',
    'trace_cross_service_relationships', 'analyze_architecture_boundaries',
    'calculate_change_impact', 'find_all_paths_between_symbols',

    # Repository Intelligence Tools (14)
    'identify_entry_points', 'detect_build_system', 'detect_package_manager',
    'detect_project_type', 'analyze_monorepo', 'analyze_project_configuration',
    'analyze_build_configuration', 'analyze_environment_configuration',
    'analyze_dependencies_manifest', 'resolve_dependency_versions',
    'identify_external_services', 'identify_generated_files',
    'incremental_index_repository', 'detect_repository_changes',

    # Code Understanding Tools (12)
    'explain_class', 'explain_module', 'explain_variable', 'explain_expression',
    'explain_condition', 'explain_algorithm', 'extract_function_contract',
    'identify_hidden_assumptions', 'infer_code_intent', 'compare_implementations',
    'trace_function_logic', 'generate_code_summary',
]

def main():
    test_root = Path(__file__).parent.parent
    generator = TestSpecGenerator(test_root)
    generator.load_all_tool_signatures()

    # Generate Layer 1 tests (T01-T09) for all Priority 1 tools
    test_types = [f'T0{i}' for i in range(1, 10)]

    total_specs = 0
    failed_tools = []

    for tool_name in PRIORITY_1_TOOLS:
        print(f"Generating Layer 1 tests for {tool_name}...")

        try:
            specs = generator.generate_for_tool(tool_name, test_types)
            saved = generator.save_specs(specs, test_root / 'tests')
            total_specs += len(saved)
            print(f"  Saved {len(saved)} specs")
        except Exception as e:
            import traceback
            print(f"  ERROR: {e}")
            traceback.print_exc()
            failed_tools.append(tool_name)

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
