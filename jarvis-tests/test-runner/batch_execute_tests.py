#!/Library/Frameworks/Python.framework/Versions/3.13/bin/python3
"""
Batch execute tests against real tool implementations
"""
import sys
from pathlib import Path
import yaml
import json
from datetime import datetime

# Add server to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from server.ai_agents.tools import (
    repository_tools,
    code_understanding_tools,
    relationship_intelligence_tools,
    repository_intelligence_tools,
    analysis_tools,
    git_tools,
    data_flow_intelligence_tools,
    navigation_tools,
    testing_verification_tools,
    software_engineering_tools
)
from google.adk.tools import ToolContext

# Absolute paths
WORKSPACE = Path('/Users/adarsh/Documents/vr-agent')

# Mock ToolContext for testing
class MockToolContext:
    def __init__(self):
        self.state = {'evidence': []}

# Tool mapping
TOOL_FUNCTIONS = {
    'read_file': repository_tools.read_file,
    'list_files': repository_tools.list_files,
    'search_files': repository_tools.search_files,
    'search_code': repository_tools.search_code,
    'read_file_range': repository_tools.read_file_range,
    'parse_source_code': code_understanding_tools.parse_source_code,
    'find_callers': relationship_intelligence_tools.find_callers,
    'find_callees': relationship_intelligence_tools.find_callees,
    'find_indirect_callers': relationship_intelligence_tools.find_indirect_callers,
    'build_call_graph': relationship_intelligence_tools.build_call_graph,
    'build_dependency_graph': relationship_intelligence_tools.build_dependency_graph,
    'explain_function': code_understanding_tools.explain_function,
    'explain_class': code_understanding_tools.explain_class,
    'explain_module': code_understanding_tools.explain_module,
    'analyze_build_configuration': repository_intelligence_tools.analyze_build_configuration,
    'analyze_dependencies_manifest': repository_intelligence_tools.analyze_dependencies_manifest,
    'analyze_environment_configuration': repository_intelligence_tools.analyze_environment_configuration,
    'analyze_monorepo': repository_intelligence_tools.analyze_monorepo,
    'analyze_project_configuration': repository_intelligence_tools.analyze_project_configuration,
    'detect_build_system': repository_intelligence_tools.detect_build_system,
    'detect_package_manager': repository_intelligence_tools.detect_package_manager,
    'detect_project_type': repository_intelligence_tools.detect_project_type,
    'detect_repository_changes': repository_intelligence_tools.detect_repository_changes,
    'identify_entry_points': repository_intelligence_tools.identify_entry_points,
    'analyze_annotations': analysis_tools.analyze_annotations,
    'analyze_code_complexity': analysis_tools.analyze_code_complexity,
    'analyze_data_flow': analysis_tools.analyze_data_flow,
    'analyze_dependencies': analysis_tools.analyze_dependencies,
    'analyze_exceptions': analysis_tools.analyze_exceptions,
    'analyze_generated_code': analysis_tools.analyze_generated_code,
    'analyze_macros': analysis_tools.analyze_macros,
    'measure_test_coverage': testing_verification_tools.measure_test_coverage,
    'measure_branch_coverage': testing_verification_tools.measure_branch_coverage,
    'discover_tests': testing_verification_tools.discover_tests,
    'run_unit_tests': testing_verification_tools.run_unit_tests,
    'verify_compilation': testing_verification_tools.verify_compilation,
    'create_file': software_engineering_tools.create_file,
    'edit_file': software_engineering_tools.edit_file,
    'delete_file': software_engineering_tools.delete_file,
    'move_file': software_engineering_tools.move_file,
    'rename_file': software_engineering_tools.rename_file,
    'create_directory': software_engineering_tools.create_directory,
    'execute_command': software_engineering_tools.execute_command,
    'git_diff': software_engineering_tools.git_diff,
    'git_log': software_engineering_tools.git_log,
    'git_status': software_engineering_tools.git_status,
    'git_branch': software_engineering_tools.git_branch,
    'git_commit': software_engineering_tools.git_commit,
    'git_show': software_engineering_tools.git_show,
    'run_build': software_engineering_tools.run_build,
    'run_linter': software_engineering_tools.run_linter,
    'run_formatter': software_engineering_tools.run_formatter,
    'run_type_checker': software_engineering_tools.run_type_checker,
    'get_diff': git_tools.get_diff,
    'get_branch_info': git_tools.get_branch_info,
    'list_changed_nodes': git_tools.list_changed_nodes,
}

def execute_test(test_def):
    """Execute a single test"""
    test_id = test_def.get('test_id')
    tool_name = test_def.get('tool')
    category = test_def.get('category')

    # Check if tool is available
    if tool_name not in TOOL_FUNCTIONS:
        return {
            'test_id': test_id,
            'status': 'skipped',
            'reason': f'Tool {tool_name} not mapped'
        }

    # Check for placeholder inputs
    input_data = test_def.get('input', {})
    has_placeholder = any(str(v).lower() == 'placeholder' for v in input_data.values())

    if has_placeholder:
        return {
            'test_id': test_id,
            'status': 'skipped',
            'reason': 'Placeholder inputs'
        }

    # Execute tool
    try:
        tool_func = TOOL_FUNCTIONS[tool_name]
        tool_context = MockToolContext()

        # Call tool with appropriate arguments
        if tool_name == 'read_file':
            file_path = input_data.get('file_path')
            if not Path(file_path).is_absolute():
                full_path = WORKSPACE / file_path
            else:
                full_path = Path(file_path)
            result = tool_func(str(full_path), tool_context)
        elif tool_name == 'list_files':
            directory = input_data.get('directory', '.')
            if not Path(directory).is_absolute():
                full_path = WORKSPACE / directory
            else:
                full_path = Path(directory)
            result = tool_func(tool_context, str(full_path))
        elif tool_name == 'read_file_range':
            file_path = input_data.get('file_path')
            start_line = input_data.get('start_line')
            end_line = input_data.get('end_line')
            if not Path(file_path).is_absolute():
                full_path = WORKSPACE / file_path
            else:
                full_path = Path(file_path)
            result = tool_func(str(full_path), start_line, end_line, tool_context)
        elif tool_name == 'parse_source_code':
            file_path = input_data.get('file_path')
            if not Path(file_path).is_absolute():
                full_path = WORKSPACE / file_path
            else:
                full_path = Path(file_path)
            result = tool_func(str(full_path), tool_context)
        elif tool_name in ['find_callers', 'find_callees', 'find_indirect_callers']:
            function_id = input_data.get('function_id')
            result = tool_func(function_id, tool_context)
        elif tool_name == 'build_call_graph':
            file_path = input_data.get('file_path')
            if not Path(file_path).is_absolute():
                full_path = WORKSPACE / file_path
            else:
                full_path = Path(file_path)
            result = tool_func(str(full_path), tool_context)
        elif tool_name == 'build_dependency_graph':
            directory = input_data.get('directory', '.')
            if not Path(directory).is_absolute():
                full_path = WORKSPACE / directory
            else:
                full_path = Path(directory)
            result = tool_func(str(full_path), tool_context)
        elif tool_name in ['explain_function', 'explain_class', 'explain_module']:
            identifier = input_data.get('function_id') or input_data.get('class_id') or input_data.get('file_path')
            result = tool_func(identifier, tool_context)
        elif tool_name in ['analyze_build_configuration', 'analyze_dependencies_manifest', 'analyze_environment_configuration', 'analyze_monorepo', 'analyze_project_configuration']:
            repository_path = input_data.get('repository_path')
            if not Path(repository_path).is_absolute():
                full_path = WORKSPACE / repository_path
            else:
                full_path = Path(repository_path)
            result = tool_func(str(full_path), tool_context)
        elif tool_name in ['detect_build_system', 'detect_package_manager', 'detect_project_type', 'detect_repository_changes', 'identify_entry_points']:
            repository_path = input_data.get('repository_path')
            if not Path(repository_path).is_absolute():
                full_path = WORKSPACE / repository_path
            else:
                full_path = Path(repository_path)
            result = tool_func(str(full_path), tool_context)
        elif tool_name in ['analyze_annotations', 'analyze_code_complexity', 'analyze_data_flow', 'analyze_dependencies', 'analyze_exceptions', 'analyze_generated_code', 'analyze_macros']:
            file_path = input_data.get('file_path')
            if not Path(file_path).is_absolute():
                full_path = WORKSPACE / file_path
            else:
                full_path = Path(file_path)
            result = tool_func(str(full_path), tool_context)
        elif tool_name == 'get_branch_info':
            repository_path = input_data.get('repository_path')
            if not Path(repository_path).is_absolute():
                full_path = WORKSPACE / repository_path
            else:
                full_path = Path(repository_path)
            result = tool_func(str(full_path), tool_context)
        elif tool_name == 'get_diff':
            repository_path = input_data.get('repository_path')
            if not Path(repository_path).is_absolute():
                full_path = WORKSPACE / repository_path
            else:
                full_path = Path(repository_path)
            result = tool_func(str(full_path), tool_context)
        elif tool_name == 'measure_test_coverage':
            repository_path = input_data.get('repository_path')
            if not Path(repository_path).is_absolute():
                full_path = WORKSPACE / repository_path
            else:
                full_path = Path(repository_path)
            result = tool_func(str(full_path), tool_context)
        elif tool_name == 'measure_branch_coverage':
            repository_path = input_data.get('repository_path')
            if not Path(repository_path).is_absolute():
                full_path = WORKSPACE / repository_path
            else:
                full_path = Path(repository_path)
            result = tool_func(str(full_path), tool_context)
        elif tool_name == 'discover_tests':
            repository_path = input_data.get('repository_path')
            if not Path(repository_path).is_absolute():
                full_path = WORKSPACE / repository_path
            else:
                full_path = Path(repository_path)
            result = tool_func(str(full_path), tool_context)
        elif tool_name == 'run_unit_tests':
            repository_path = input_data.get('repository_path')
            if not Path(repository_path).is_absolute():
                full_path = WORKSPACE / repository_path
            else:
                full_path = Path(repository_path)
            result = tool_func(str(full_path), tool_context)
        elif tool_name == 'verify_compilation':
            repository_path = input_data.get('repository_path')
            if not Path(repository_path).is_absolute():
                full_path = WORKSPACE / repository_path
            else:
                full_path = Path(repository_path)
            result = tool_func(str(full_path), tool_context)
        elif tool_name in ['create_file', 'edit_file', 'delete_file', 'move_file', 'rename_file', 'create_directory']:
            file_path = input_data.get('file_path')
            if not Path(file_path).is_absolute():
                full_path = WORKSPACE / file_path
            else:
                full_path = Path(file_path)
            if tool_name == 'edit_file':
                old_content = input_data.get('old_content', '')
                new_content = input_data.get('new_content', '')
                result = tool_func(str(full_path), old_content, new_content, tool_context)
            elif tool_name == 'create_file':
                content = input_data.get('content', '')
                result = tool_func(str(full_path), content, tool_context)
            else:
                result = tool_func(str(full_path), tool_context)
        elif tool_name == 'execute_command':
            command = input_data.get('command', '')
            result = tool_func(command, tool_context)
        elif tool_name in ['git_diff', 'git_log', 'git_status', 'git_branch', 'git_commit', 'git_show']:
            repository_path = input_data.get('repository_path', WORKSPACE)
            if not Path(repository_path).is_absolute():
                full_path = WORKSPACE / repository_path
            else:
                full_path = Path(repository_path)
            if tool_name == 'git_commit':
                message = input_data.get('message', '')
                result = tool_func(str(full_path), message, tool_context)
            else:
                result = tool_func(str(full_path), tool_context)
        elif tool_name in ['run_build', 'run_linter', 'run_formatter', 'run_type_checker']:
            repository_path = input_data.get('repository_path', WORKSPACE)
            if not Path(repository_path).is_absolute():
                full_path = WORKSPACE / repository_path
            else:
                full_path = Path(repository_path)
            result = tool_func(str(full_path), tool_context)
        elif tool_name in ['get_diff', 'get_branch_info', 'list_changed_nodes']:
            # These tools only take tool_context
            result = tool_func(tool_context)
        else:
            result = {'status': 'skipped', 'reason': f'Tool {tool_name} not fully implemented in runner'}

        # Check result
        expected = test_def.get('expected', {})
        result_status = result.get('status')
        expected_status = expected.get('status')

        if result_status == expected_status:
            return {
                'test_id': test_id,
                'status': 'passed',
                'result': result
            }
        else:
            return {
                'test_id': test_id,
                'status': 'failed',
                'reason': f'Expected status {expected_status}, got {result_status}',
                'expected': expected,
                'actual': result
            }

    except Exception as e:
        return {
            'test_id': test_id,
            'status': 'error',
            'error': str(e)
        }

def main():
    # Process multiple test directories
    test_dirs = [
        'jarvis-tests/tests/core-tools',
        'jarvis-tests/tests/real-input/relationship',
        'jarvis-tests/tests/real-input/code_understanding',
        'jarvis-tests/tests/unit/relationships',
        'jarvis-tests/tests/layer1/code_understanding',
        'jarvis-tests/tests/layer1/relationship',
        'jarvis-tests/tests/layer1/repository_intelligence',
        'jarvis-tests/tests/real-input/repository_intelligence',
        'jarvis-tests/tests/layer1/analysis',
        'jarvis-tests/tests/layer2',
        'jarvis-tests/tests/repository_intelligence',
        'jarvis-tests/tests/security_quality',
        'jarvis-tests/tests/layer3',
        'jarvis-tests/tests/layer4',
        'jarvis-tests/tests/layer5',
        'jarvis-tests/tests/layer6',
        'jarvis-tests/tests/layer7',
        'jarvis-tests/tests/integration',
        'jarvis-tests/tests/stress',
        'jarvis-tests/tests/multi-agent',
        'jarvis-tests/tests/end-to-end',
        'jarvis-tests/tests/agent-capabilities',
        'jarvis-tests/tests/chaos',
        'jarvis-tests/tests/code_understanding',
        'jarvis-tests/tests/load',
        'jarvis-tests/tests/phase2_core_tools',
        'jarvis-tests/tests/regression',
        'jarvis-tests/tests/security',
        'jarvis-tests/tests/verified',
    ]

    all_tests = []
    for test_dir in test_dirs:
        tests_path = WORKSPACE / test_dir
        if not tests_path.exists():
            print(f"Skipping {test_dir} (not found)")
            continue

        print(f"Loading tests from: {tests_path}")
        for yaml_file in tests_path.rglob('*.yaml'):
            try:
                with open(yaml_file) as f:
                    test_def = yaml.safe_load(f)
                if test_def and test_def.get('test_id'):
                    # Only load tests for tools we can execute
                    if test_def.get('tool') in TOOL_FUNCTIONS:
                        all_tests.append(test_def)
            except Exception as e:
                pass

    print(f"Loaded {len(all_tests)} tests (filtered for available tools)")

    # Execute all available tests (no limit)
    tests = all_tests
    print(f"Executing {len(tests)} tests")

    # Execute tests
    results = []
    passed = 0
    failed = 0
    skipped = 0
    errors = 0

    for i, test in enumerate(tests):
        result = execute_test(test)
        results.append(result)

        if result['status'] == 'passed':
            passed += 1
            print(f"  {result['test_id']}: PASSED")
        elif result['status'] == 'failed':
            failed += 1
            print(f"  {result['test_id']}: FAILED - {result.get('reason', 'unknown')}")
        elif result['status'] == 'skipped':
            skipped += 1
            print(f"  {result['test_id']}: SKIPPED - {result.get('reason', 'unknown')}")
        elif result['status'] == 'error':
            errors += 1
            print(f"  {result['test_id']}: ERROR - {result.get('error', 'unknown')}")

        if (i + 1) % 10 == 0:
            print(f"  Processed {i + 1}/{len(tests)} tests...")

    # Summary
    print(f"\nSummary:")
    print(f"  Total: {len(results)}")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors: {errors}")
    print(f"  Success Rate: {passed / len(results) * 100:.2f}%")

    # Save results
    report_path = WORKSPACE / 'jarvis-tests/test-reports/batch_execution.json'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total': len(results),
                'passed': passed,
                'failed': failed,
                'skipped': skipped,
                'errors': errors,
                'success_rate': passed / len(results) * 100 if results else 0
            },
            'results': results
        }, f, indent=2)
    print(f"Report saved to: {report_path}")

if __name__ == '__main__':
    main()
