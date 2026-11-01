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

from server.ai_agents.tools import (
    repository_tools, code_understanding_tools, relationship_intelligence_tools,
    repository_intelligence_tools, analysis_tools, testing_verification_tools,
    software_engineering_tools, git_tools, data_flow_intelligence_tools,
    api_database_toolkit, debugging_intelligence_tools, documentation_toolkit,
    external_integrations_toolkit, git_history_toolkit, graph_tools,
    infrastructure_services, language_adapters, memory_tools, navigation_tools,
    orchestrator_tools, runtime_intelligence_tools, scene_tools,
    security_quality_tools, visualization_spatial_tools, vr_specific_tools,
    conversational_tools, control_tools, exec_tools
)
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
    'trace_variable_origin': data_flow_intelligence_tools.trace_variable_origin,
    'trace_variable_usage': data_flow_intelligence_tools.trace_variable_usage,
    'trace_variable_modifications': data_flow_intelligence_tools.trace_variable_modifications,
    'trace_parameter_flow': data_flow_intelligence_tools.trace_parameter_flow,
    'trace_return_value_flow': data_flow_intelligence_tools.trace_return_value_flow,
    'trace_transformations': data_flow_intelligence_tools.trace_transformations,
    'trace_cross_function_flow': data_flow_intelligence_tools.trace_cross_function_flow,
    'trace_cross_service_flow': data_flow_intelligence_tools.trace_cross_service_flow,
    'trace_database_reads': data_flow_intelligence_tools.trace_database_reads,
    'trace_database_writes': data_flow_intelligence_tools.trace_database_writes,
    'trace_api_data_flow': data_flow_intelligence_tools.trace_api_data_flow,
    'trace_file_operations': data_flow_intelligence_tools.trace_file_operations,
    'trace_state_changes': data_flow_intelligence_tools.trace_state_changes,
    'build_data_flow_graph': data_flow_intelligence_tools.build_data_flow_graph,
    'identify_data_sinks': data_flow_intelligence_tools.identify_data_sinks,
    'identify_data_sources': data_flow_intelligence_tools.identify_data_sources,
    'identify_data_leaks': data_flow_intelligence_tools.identify_data_leaks,
    'identify_validation_gaps': data_flow_intelligence_tools.identify_validation_gaps,
    # API/Database tools
    'discover_api_endpoints': api_database_toolkit.discover_api_endpoints,
    'inspect_api_schema': api_database_toolkit.inspect_api_schema,
    'analyze_api_contract': api_database_toolkit.analyze_api_contract,
    'trace_api_call': api_database_toolkit.trace_api_call,
    'analyze_api_security': api_database_toolkit.analyze_api_security,
    'inspect_http_routes': api_database_toolkit.inspect_http_routes,
    'inspect_middleware': api_database_toolkit.inspect_middleware,
    'inspect_authentication': api_database_toolkit.inspect_authentication,
    'inspect_authorization': api_database_toolkit.inspect_authorization,
    # Debugging tools
    'capture_exception': debugging_intelligence_tools.capture_exception,
    'analyze_stack_trace': debugging_intelligence_tools.analyze_stack_trace,
    'find_error_origin': debugging_intelligence_tools.find_error_origin,
    'trace_error_propagation': debugging_intelligence_tools.trace_error_propagation,
    'identify_failure_path': debugging_intelligence_tools.identify_failure_path,
    'set_breakpoint': debugging_intelligence_tools.set_breakpoint,
    'remove_breakpoint': debugging_intelligence_tools.remove_breakpoint,
    'step_into': debugging_intelligence_tools.step_into,
    'step_over': debugging_intelligence_tools.step_over,
    'step_out': debugging_intelligence_tools.step_out,
    # Documentation tools
    'search_documentation': documentation_toolkit.search_documentation,
    'generate_code_documentation': documentation_toolkit.generate_code_documentation,
    'extract_docstrings': documentation_toolkit.extract_docstrings,
    'verify_documentation_coverage': documentation_toolkit.verify_documentation_coverage,
    'read_documentation': documentation_toolkit.read_documentation,
    'search_external_docs': documentation_toolkit.search_external_docs,
    'search_library_docs': documentation_toolkit.search_library_docs,
    'search_framework_docs': documentation_toolkit.search_framework_docs,
    'search_api_docs': documentation_toolkit.search_api_docs,
    'search_issues': documentation_toolkit.search_issues,
    # External integrations
    'github_get_repository': external_integrations_toolkit.github_get_repository,
    'github_get_issues': external_integrations_toolkit.github_get_issues,
    'github_get_pull_requests': external_integrations_toolkit.github_get_pull_requests,
    'github_get_commits': external_integrations_toolkit.github_get_commits,
    'get_ci_status': external_integrations_toolkit.get_ci_status,
    'trigger_ci_build': external_integrations_toolkit.trigger_ci_build,
    'get_ci_logs': external_integrations_toolkit.get_ci_logs,
    'cancel_ci_build': external_integrations_toolkit.cancel_ci_build,
    'docker_list_containers': external_integrations_toolkit.docker_list_containers,
    'docker_get_container_logs': external_integrations_toolkit.docker_get_container_logs,
    # Git history
    'find_introducing_commit': git_history_toolkit.find_introducing_commit,
    'analyze_commit_impact': git_history_toolkit.analyze_commit_impact,
    'trace_file_history': git_history_toolkit.trace_file_history,
    # Graph tools
    'search_graph_symbols': graph_tools.search_graph_symbols,
    'get_node': graph_tools.get_node,
    'get_callers': graph_tools.get_callers,
    'get_callees': graph_tools.get_callees,
    'get_dependents': graph_tools.get_dependents,
    # Infrastructure
    'check_permission': infrastructure_services.check_permission,
    'grant_permission': infrastructure_services.grant_permission,
    'revoke_permission': infrastructure_services.revoke_permission,
    'list_permissions': infrastructure_services.list_permissions,
    'set_permission_level': infrastructure_services.set_permission_level,
    'request_sensitive_approval': infrastructure_services.request_sensitive_approval,
    'check_approval_status': infrastructure_services.check_approval_status,
    'register_tool': infrastructure_services.register_tool,
    'unregister_tool': infrastructure_services.unregister_tool,
    'get_tool_definition': infrastructure_services.get_tool_definition,
    # Language adapters
    'register_language_adapter': language_adapters.register_language_adapter,
    'get_language_adapter': language_adapters.get_language_adapter,
    'list_supported_languages': language_adapters.list_supported_languages,
    'parse_language_ast': language_adapters.parse_language_ast,
    'resolve_language_types': language_adapters.resolve_language_types,
    'extract_language_symbols': language_adapters.extract_language_symbols,
    'analyze_language_specific_features': language_adapters.analyze_language_specific_features,
    'register_framework_adapter': language_adapters.register_framework_adapter,
    'get_framework_adapter': language_adapters.get_framework_adapter,
    'list_supported_frameworks': language_adapters.list_supported_frameworks,
    # Memory tools
    'load_project_memory': memory_tools.load_project_memory,
    'save_finding': memory_tools.save_finding,
    'record_decision': memory_tools.record_decision,
    # Navigation
    'get_symbol_definition': navigation_tools.get_symbol_definition,
    'get_symbol_references': navigation_tools.get_symbol_references,
    'get_symbol_hover_info': navigation_tools.get_symbol_hover_info,
    'get_call_hierarchy': navigation_tools.get_call_hierarchy,
    'get_type_hierarchy': navigation_tools.get_type_hierarchy,
    'get_imports': navigation_tools.get_imports,
    # Orchestrator
    'understand_user_intent': orchestrator_tools.understand_user_intent,
    'classify_request': orchestrator_tools.classify_request,
    'create_investigation_plan': orchestrator_tools.create_investigation_plan,
    'decompose_task': orchestrator_tools.decompose_task,
    'select_agents': orchestrator_tools.select_agents,
    'delegate_task': orchestrator_tools.delegate_task,
    'run_agents_parallel': orchestrator_tools.run_agents_parallel,
    'run_agents_sequentially': orchestrator_tools.run_agents_sequentially,
    'wait_for_agent': orchestrator_tools.wait_for_agent,
    'get_agent_status': orchestrator_tools.get_agent_status,
    # Runtime
    'start_application': runtime_intelligence_tools.start_application,
    'stop_application': runtime_intelligence_tools.stop_application,
    'attach_runtime_profiler': runtime_intelligence_tools.attach_runtime_profiler,
    'attach_debugger': runtime_intelligence_tools.attach_debugger,
    'collect_execution_trace': runtime_intelligence_tools.collect_execution_trace,
    'record_function_calls': runtime_intelligence_tools.record_function_calls,
    'record_function_arguments': runtime_intelligence_tools.record_function_arguments,
    'record_function_returns': runtime_intelligence_tools.record_function_returns,
    'record_execution_timing': runtime_intelligence_tools.record_execution_timing,
    'record_variable_state': runtime_intelligence_tools.record_variable_state,
    # Scene tools
    'highlight_vr_path': scene_tools.highlight_vr_path,
    'dim_unrelated': scene_tools.dim_unrelated,
    'focus_camera': scene_tools.focus_camera,
    'open_code_panel': scene_tools.open_code_panel,
    'set_edge_style': scene_tools.set_edge_style,
    'show_ghost_diff': scene_tools.show_ghost_diff,
    'show_test_badges': scene_tools.show_test_badges,
    'show_approval_prompt': scene_tools.show_approval_prompt,
    # Security
    'scan_secrets': security_quality_tools.scan_secrets,
    'scan_vulnerabilities': security_quality_tools.scan_vulnerabilities,
    'check_code_quality': security_quality_tools.check_code_quality,
    'scan_dependency_vulnerabilities': security_quality_tools.scan_dependency_vulnerabilities,
    'analyze_authentication': security_quality_tools.analyze_authentication,
    'analyze_authorization': security_quality_tools.analyze_authorization,
    'analyze_permissions': security_quality_tools.analyze_permissions,
    'analyze_input_validation': security_quality_tools.analyze_input_validation,
    # Visualization
    'create_graph': visualization_spatial_tools.create_graph,
    'add_graph_node': visualization_spatial_tools.add_graph_node,
    'remove_graph_node': visualization_spatial_tools.remove_graph_node,
    'add_graph_edge': visualization_spatial_tools.add_graph_edge,
    'remove_graph_edge': visualization_spatial_tools.remove_graph_edge,
    'expand_graph_node': visualization_spatial_tools.expand_graph_node,
    'collapse_graph_node': visualization_spatial_tools.collapse_graph_node,
    'filter_graph': visualization_spatial_tools.filter_graph,
    'search_graph': visualization_spatial_tools.search_graph,
    # VR tools
    'get_vr_session_state': vr_specific_tools.get_vr_session_state,
    'get_selected_object': vr_specific_tools.get_selected_object,
    'process_voice_command': vr_specific_tools.process_voice_command,
    'register_voice_command': vr_specific_tools.register_voice_command,
    'list_voice_commands': vr_specific_tools.list_voice_commands,
    'set_hand_interaction_mode': vr_specific_tools.set_hand_interaction_mode,
    'get_hand_interaction_state': vr_specific_tools.get_hand_interaction_state,
    'set_spatial_audio': vr_specific_tools.set_spatial_audio,
    'set_haptic_feedback': vr_specific_tools.set_haptic_feedback,
    'set_vr_environment': vr_specific_tools.set_vr_environment,
    # Conversational
    'speech_to_text': conversational_tools.speech_to_text,
    'text_to_speech': conversational_tools.text_to_speech,
    'stream_voice_response': conversational_tools.stream_voice_response,
    'detect_speaker_intent': conversational_tools.detect_speaker_intent,
    'detect_voice_activity': conversational_tools.detect_voice_activity,
    'manage_conversation': conversational_tools.manage_conversation,
    'retrieve_conversation_context': conversational_tools.retrieve_conversation_context,
    # Control
    'request_approval': control_tools.request_approval,
    'exit_loop': control_tools.exit_loop,
    # Exec tools
    'run_tests': exec_tools.run_tests,
    'run_typecheck': exec_tools.run_typecheck,
    'read_test_results': exec_tools.read_test_results,
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
