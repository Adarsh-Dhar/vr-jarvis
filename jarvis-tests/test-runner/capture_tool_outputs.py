#!/Library/Frameworks/Python.framework/Versions/3.13/bin/python3
"""
Execute tools with real inputs and capture outputs for test specs
"""
import sys
from pathlib import Path
import yaml
import json
from datetime import datetime

# Add server to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from server.ai_agents.tools import repository_tools, code_understanding_tools, relationship_intelligence_tools, repository_intelligence_tools, analysis_tools, testing_verification_tools, software_engineering_tools, git_tools
from google.adk.tools import ToolContext

# Absolute paths
WORKSPACE = Path('/Users/adarsh/Documents/vr-agent')
FIXTURES_ROOT = WORKSPACE / 'jarvis-tests/fixtures/repositories'

# Mock ToolContext
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
    'parse_function': code_understanding_tools.parse_function,
    'extract_function_signature': code_understanding_tools.extract_function_signature,
    'get_symbol_definition': code_understanding_tools.get_symbol_definition,
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

def execute_tool(tool_name, input_data):
    """Execute a tool with given input data"""
    tool_func = TOOL_FUNCTIONS.get(tool_name)
    if not tool_func:
        return None

    tool_context = MockToolContext()

    try:
        if tool_name == 'read_file':
            file_path = input_data.get('file_path')
            # Convert relative path to absolute
            if not Path(file_path).is_absolute():
                full_path = WORKSPACE / file_path
            else:
                full_path = Path(file_path)
            return tool_func(str(full_path), tool_context)
        elif tool_name == 'list_files':
            directory = input_data.get('directory', '.')
            # Convert relative path to absolute
            if not Path(directory).is_absolute():
                full_path = WORKSPACE / directory
            else:
                full_path = Path(directory)
            return tool_func(tool_context, str(full_path))
        elif tool_name == 'read_file_range':
            file_path = input_data.get('file_path')
            start_line = input_data.get('start_line', 1)
            end_line = input_data.get('end_line', 10)
            # Convert relative path to absolute
            if not Path(file_path).is_absolute():
                full_path = WORKSPACE / file_path
            else:
                full_path = Path(file_path)
            return tool_func(str(full_path), start_line, end_line, tool_context)
        elif tool_name == 'parse_source_code':
            file_path = input_data.get('file_path')
            # Convert relative path to absolute
            if not Path(file_path).is_absolute():
                full_path = WORKSPACE / file_path
            else:
                full_path = Path(file_path)
            return tool_func(str(full_path), tool_context)
        elif tool_name == 'parse_function':
            file_path = input_data.get('file_path')
            function_name = input_data.get('function_name')
            # Convert relative path to absolute
            if not Path(file_path).is_absolute():
                full_path = WORKSPACE / file_path
            else:
                full_path = Path(file_path)
            return tool_func(str(full_path), function_name, tool_context)
        elif tool_name == 'extract_function_signature':
            file_path = input_data.get('file_path')
            function_name = input_data.get('function_name')
            # Convert relative path to absolute
            if not Path(file_path).is_absolute():
                full_path = WORKSPACE / file_path
            else:
                full_path = Path(file_path)
            return tool_func(str(full_path), function_name, tool_context)
        elif tool_name == 'get_symbol_definition':
            file_path = input_data.get('file_path')
            symbol_name = input_data.get('symbol_name')
            # Convert relative path to absolute
            if not Path(file_path).is_absolute():
                full_path = WORKSPACE / file_path
            else:
                full_path = Path(file_path)
            return tool_func(str(full_path), symbol_name, tool_context)
        elif tool_name in ['find_callers', 'find_callees', 'find_indirect_callers']:
            function_id = input_data.get('function_id')
            return tool_func(function_id, tool_context)
        elif tool_name == 'build_call_graph':
            file_path = input_data.get('file_path')
            # Convert relative path to absolute
            if not Path(file_path).is_absolute():
                full_path = WORKSPACE / file_path
            else:
                full_path = Path(file_path)
            return tool_func(str(full_path), tool_context)
        elif tool_name == 'build_dependency_graph':
            directory = input_data.get('directory', '.')
            # Convert relative path to absolute
            if not Path(directory).is_absolute():
                full_path = WORKSPACE / directory
            else:
                full_path = Path(directory)
            return tool_func(str(full_path), tool_context)
        elif tool_name in ['explain_function', 'explain_class', 'explain_module']:
            identifier = input_data.get('function_id') or input_data.get('class_id') or input_data.get('file_path')
            return tool_func(identifier, tool_context)
        elif tool_name in ['analyze_build_configuration', 'analyze_dependencies_manifest', 'analyze_environment_configuration', 'analyze_monorepo', 'analyze_project_configuration']:
            repository_path = input_data.get('repository_path')
            if not Path(repository_path).is_absolute():
                full_path = WORKSPACE / repository_path
            else:
                full_path = Path(repository_path)
            return tool_func(str(full_path), tool_context)
        elif tool_name in ['detect_build_system', 'detect_package_manager', 'detect_project_type', 'detect_repository_changes', 'identify_entry_points']:
            repository_path = input_data.get('repository_path')
            if not Path(repository_path).is_absolute():
                full_path = WORKSPACE / repository_path
            else:
                full_path = Path(repository_path)
            return tool_func(str(full_path), tool_context)
        elif tool_name in ['analyze_annotations', 'analyze_code_complexity', 'analyze_data_flow', 'analyze_dependencies', 'analyze_exceptions', 'analyze_generated_code', 'analyze_macros']:
            file_path = input_data.get('file_path')
            if not Path(file_path).is_absolute():
                full_path = WORKSPACE / file_path
            else:
                full_path = Path(file_path)
            return tool_func(str(full_path), tool_context)
        elif tool_name == 'get_branch_info':
            repository_path = input_data.get('repository_path')
            if not Path(repository_path).is_absolute():
                full_path = WORKSPACE / repository_path
            else:
                full_path = Path(repository_path)
            return tool_func(str(full_path), tool_context)
        elif tool_name == 'get_diff':
            repository_path = input_data.get('repository_path')
            if not Path(repository_path).is_absolute():
                full_path = WORKSPACE / repository_path
            else:
                full_path = Path(repository_path)
            return tool_func(str(full_path), tool_context)
        elif tool_name == 'measure_test_coverage':
            repository_path = input_data.get('repository_path')
            if not Path(repository_path).is_absolute():
                full_path = WORKSPACE / repository_path
            else:
                full_path = Path(repository_path)
            return tool_func(str(full_path), tool_context)
        elif tool_name == 'measure_branch_coverage':
            repository_path = input_data.get('repository_path')
            if not Path(repository_path).is_absolute():
                full_path = WORKSPACE / repository_path
            else:
                full_path = Path(repository_path)
            return tool_func(str(full_path), tool_context)
        elif tool_name == 'discover_tests':
            repository_path = input_data.get('repository_path')
            if not Path(repository_path).is_absolute():
                full_path = WORKSPACE / repository_path
            else:
                full_path = Path(repository_path)
            return tool_func(str(full_path), tool_context)
        elif tool_name == 'run_unit_tests':
            repository_path = input_data.get('repository_path')
            if not Path(repository_path).is_absolute():
                full_path = WORKSPACE / repository_path
            else:
                full_path = Path(repository_path)
            return tool_func(str(full_path), tool_context)
        elif tool_name == 'verify_compilation':
            repository_path = input_data.get('repository_path')
            if not Path(repository_path).is_absolute():
                full_path = WORKSPACE / repository_path
            else:
                full_path = Path(repository_path)
            return tool_func(str(full_path), tool_context)
        elif tool_name in ['create_file', 'edit_file', 'delete_file', 'move_file', 'rename_file', 'create_directory']:
            file_path = input_data.get('file_path')
            if not Path(file_path).is_absolute():
                full_path = WORKSPACE / file_path
            else:
                full_path = Path(file_path)
            if tool_name == 'edit_file':
                old_content = input_data.get('old_content', '')
                new_content = input_data.get('new_content', '')
                return tool_func(str(full_path), old_content, new_content, tool_context)
            elif tool_name == 'create_file':
                content = input_data.get('content', '')
                return tool_func(str(full_path), content, tool_context)
            else:
                return tool_func(str(full_path), tool_context)
        elif tool_name == 'execute_command':
            command = input_data.get('command', '')
            return tool_func(command, tool_context)
        elif tool_name in ['git_diff', 'git_log', 'git_status', 'git_branch', 'git_commit', 'git_show']:
            repository_path = input_data.get('repository_path', WORKSPACE)
            if not Path(repository_path).is_absolute():
                full_path = WORKSPACE / repository_path
            else:
                full_path = Path(repository_path)
            if tool_name == 'git_commit':
                message = input_data.get('message', '')
                return tool_func(str(full_path), message, tool_context)
            else:
                return tool_func(str(full_path), tool_context)
        elif tool_name in ['run_build', 'run_linter', 'run_formatter', 'run_type_checker']:
            repository_path = input_data.get('repository_path', WORKSPACE)
            if not Path(repository_path).is_absolute():
                full_path = WORKSPACE / repository_path
            else:
                full_path = Path(repository_path)
            return tool_func(str(full_path), tool_context)
        elif tool_name in ['get_diff', 'get_branch_info', 'list_changed_nodes']:
            # These tools only take tool_context, read from global config
            return tool_func(tool_context)
        else:
            return None
    except Exception as e:
        return {'status': 'error', 'error': str(e)}

def capture_outputs_for_tests(test_path, limit=None):
    """Execute tests and capture tool outputs (with limit to avoid timeouts)"""
    outputs = {}
    count = 0
    total_files = 0

    print(f"Scanning {test_path}...")
    for yaml_file in test_path.rglob('*.yaml'):
        total_files += 1

    print(f"Found {total_files} YAML files")

    for yaml_file in test_path.rglob('*.yaml'):
        if limit and count >= limit:
            print(f"Reached limit of {limit} tests")
            break

        try:
            with open(yaml_file) as f:
                test_def = yaml.safe_load(f)

            if not test_def or not test_def.get('test_id'):
                continue

            tool = test_def.get('tool')
            if tool not in TOOL_FUNCTIONS:
                continue

            input_data = test_def.get('input', {})
            test_id = test_def['test_id']

            # Execute tool
            print(f"Executing {test_id}...")
            output = execute_tool(tool, input_data)
            if output:
                outputs[test_id] = {
                    'tool': tool,
                    'input': input_data,
                    'output': output
                }
                print(f"  Captured: {test_id}")
                count += 1

        except Exception as e:
            print(f"Error processing {yaml_file}: {e}")

    return outputs

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

    all_outputs = {}

    for test_dir in test_dirs:
        test_path = WORKSPACE / test_dir
        if not test_path.exists():
            print(f"Skipping {test_dir} (not found)")
            continue

        print(f"Capturing outputs from: {test_path}")
        # No limit for any directory - process all tests
        outputs = capture_outputs_for_tests(test_path, limit=None)
        all_outputs.update(outputs)
        print(f"  -> Captured {len(outputs)} from this directory")

    # Save outputs
    output_file = WORKSPACE / 'jarvis-tests/test-reports/captured_outputs.json'
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(all_outputs, f, indent=2)

    print(f"\nCaptured {len(all_outputs)} tool outputs total")
    print(f"Saved to: {output_file}")

if __name__ == '__main__':
    main()
