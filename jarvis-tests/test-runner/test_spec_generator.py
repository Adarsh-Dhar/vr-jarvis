"""
Test Specification Generator
Auto-generates YAML test specifications for JARVIS tools
"""

import ast
import inspect
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml
import sys


# Test categories T01-T15
TEST_CATEGORIES = {
    'T01': 'Happy Path',
    'T02': 'Input Validation',
    'T03': 'Output Validation',
    'T04': 'Empty Input',
    'T05': 'Boundary Conditions',
    'T06': 'Large Input',
    'T07': 'Complex Input',
    'T08': 'Malformed Input',
    'T09': 'Dependency Failure',
    'T10': 'Timeout',
    'T11': 'Concurrency',
    'T12': 'Security',
    'T13': 'Performance',
    'T14': 'Regression',
    'T15': 'Recovery'
}

# Tool category mappings
TOOL_CATEGORIES = {
    # Analysis Tools
    'resolve_types': 'analysis',
    'resolve_references': 'analysis',
    'analyze_data_flow': 'analysis',
    'analyze_dependencies': 'analysis',
    'analyze_code_complexity': 'analysis',
    'detect_code_duplication': 'analysis',
    'detect_dead_code': 'analysis',
    'analyze_exceptions': 'analysis',
    'analyze_annotations': 'analysis',
    'analyze_macros': 'analysis',
    'analyze_generated_code': 'analysis',

    # API Database Toolkit
    'inspect_api_schema': 'api_database',
    'analyze_api_contract': 'api_database',
    'trace_api_call': 'api_database',
    'analyze_api_security': 'api_database',
    'inspect_http_routes': 'api_database',
    'inspect_middleware': 'api_database',
    'inspect_authentication': 'api_database',
    'inspect_authorization': 'api_database',
    'discover_database_schema': 'api_database',
    'inspect_database_connection': 'api_database',
    'analyze_database_queries': 'api_database',
    'trace_database_operation': 'api_database',
    'analyze_database_performance': 'api_database',
    'inspect_database_schema': 'api_database',
    'inspect_tables': 'api_database',
    'inspect_columns': 'api_database',
    'inspect_indexes': 'api_database',
    'inspect_foreign_keys': 'api_database',
    'inspect_sql_queries': 'api_database',
    'explain_query_plan': 'api_database',
    'inspect_orm_models': 'api_database',
    'inspect_orm_relationships': 'api_database',
    'trace_transaction': 'api_database',
    'trace_migrations': 'api_database',
    'map_api_to_database': 'api_database',
    'visualize_database_schema': 'api_database',

    # Code Understanding Tools
    'explain_class': 'code_understanding',
    'explain_module': 'code_understanding',
    'explain_variable': 'code_understanding',
    'explain_expression': 'code_understanding',
    'explain_condition': 'code_understanding',
    'explain_algorithm': 'code_understanding',
    'extract_function_contract': 'code_understanding',
    'identify_hidden_assumptions': 'code_understanding',
    'infer_code_intent': 'code_understanding',
    'compare_implementations': 'code_understanding',
    'trace_function_logic': 'code_understanding',
    'generate_code_summary': 'code_understanding',

    # Data Flow Intelligence
    'trace_variable_origin': 'data_flow',
    'trace_variable_usage': 'data_flow',
    'trace_variable_modifications': 'data_flow',
    'trace_parameter_flow': 'data_flow',
    'trace_return_value_flow': 'data_flow',
    'trace_transformations': 'data_flow',
    'trace_cross_function_flow': 'data_flow',
    'trace_cross_service_flow': 'data_flow',
    'trace_database_reads': 'data_flow',
    'trace_database_writes': 'data_flow',
    'trace_api_data_flow': 'data_flow',
    'trace_file_operations': 'data_flow',
    'trace_state_changes': 'data_flow',
    'build_data_flow_graph': 'data_flow',
    'identify_data_leaks': 'data_flow',
    'identify_data_sinks': 'data_flow',
    'identify_data_sources': 'data_flow',
    'identify_validation_gaps': 'data_flow',

    # Relationship Intelligence
    'trace_call_chain': 'relationship',
    'find_indirect_callers': 'relationship',
    'find_downstream_dependencies': 'relationship',
    'find_shared_dependencies': 'relationship',
    'build_reference_graph': 'relationship',
    'build_class_relationship_graph': 'relationship',
    'find_interface_implementations': 'relationship',
    'trace_cross_module_relationships': 'relationship',
    'trace_cross_service_relationships': 'relationship',
    'analyze_architecture_boundaries': 'relationship',
    'calculate_change_impact': 'relationship',
    'find_all_paths_between_symbols': 'relationship',

    # Repository Intelligence
    'identify_entry_points': 'repository_intelligence',
    'detect_build_system': 'repository_intelligence',
    'detect_package_manager': 'repository_intelligence',
    'detect_project_type': 'repository_intelligence',
    'analyze_monorepo': 'repository_intelligence',
    'analyze_project_configuration': 'repository_intelligence',
    'analyze_build_configuration': 'repository_intelligence',
    'analyze_environment_configuration': 'repository_intelligence',
    'analyze_dependencies_manifest': 'repository_intelligence',
    'resolve_dependency_versions': 'repository_intelligence',
    'identify_external_services': 'repository_intelligence',
    'identify_generated_files': 'repository_intelligence',
    'incremental_index_repository': 'repository_intelligence',
    'detect_repository_changes': 'repository_intelligence',

    # Security Quality Tools
    'scan_dependency_vulnerabilities': 'security_quality',
    'check_code_quality': 'security_quality',
    'scan_security_vulnerabilities': 'security_quality',
    'scan_vulnerabilities': 'security_quality',
    'analyze_authentication': 'security_quality',
    'analyze_authorization': 'security_quality',
    'analyze_permissions': 'security_quality',
    'analyze_injection_risks': 'security_quality',
    'analyze_cryptography': 'security_quality',
    'trace_sensitive_data': 'security_quality',
    'analyze_attack_surface': 'security_quality',
    'analyze_boundaries': 'security_quality',
    'check_advisories': 'security_quality',
    'generate_security_report': 'security_quality',
    'calculate_complexity': 'security_quality',
    'calculate_cognitive_complexity': 'security_quality',
    'detect_code_smells': 'security_quality',
    'detect_duplicates': 'security_quality',
    'detect_anti_patterns': 'security_quality',
    'analyze_maintainability': 'security_quality',
    'analyze_testability': 'security_quality',
    'analyze_violations': 'security_quality',
    'identify_technical_debt': 'security_quality',
    'generate_quality_report': 'security_quality',
}

# Performance targets by tool category
PERFORMANCE_TARGETS = {
    'analysis': {'max_duration_ms': 2000},
    'api_database': {'max_duration_ms': 5000},
    'code_understanding': {'max_duration_ms': 3000},
    'data_flow': {'max_duration_ms': 5000},
    'relationship': {'max_duration_ms': 3000},
    'repository_intelligence': {'max_duration_ms': 10000},
    'security_quality': {'max_duration_ms': 5000},
    'default': {'max_duration_ms': 3000}
}

# Severity by test category
SEVERITY_BY_CATEGORY = {
    'T01': 'critical',
    'T02': 'critical',
    'T03': 'critical',
    'T04': 'high',
    'T05': 'high',
    'T06': 'medium',
    'T07': 'high',
    'T08': 'critical',
    'T09': 'high',
    'T10': 'high',
    'T11': 'high',
    'T12': 'critical',
    'T13': 'medium',
    'T14': 'high',
    'T15': 'high'
}


class TestSpecGenerator:
    """Generates YAML test specifications for tools"""

    def __init__(self, test_root: Path):
        self.test_root = test_root
        self.tools_module = None
        self.tools_signatures = {}

    def load_tools_module(self):
        """Load the tools module to introspect tool signatures"""
        # We'll parse tool files directly instead of importing
        # to avoid circular dependency issues
        self.tools_signatures = {}
        return True

    def parse_tool_file(self, file_path: Path) -> Dict[str, Dict]:
        """Parse a tool file to extract function signatures"""
        signatures = {}

        try:
            with open(file_path, 'r') as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and not node.name.startswith('_'):
                    params = []
                    for arg in node.args.args:
                        param_info = {
                            'name': arg.arg,
                            'type': 'Any',  # Would need type inference for actual types
                            'required': True,
                            'default': None
                        }
                        params.append(param_info)

                    # Check for defaults
                    defaults_offset = len(node.args.args) - len(node.args.defaults)
                    for i, default in enumerate(node.args.defaults):
                        idx = defaults_offset + i
                        if idx < len(params):
                            params[idx]['required'] = False
                            try:
                                if hasattr(ast, 'unparse'):
                                    params[idx]['default'] = ast.unparse(default)
                                else:
                                    params[idx]['default'] = repr(default)
                            except:
                                params[idx]['default'] = 'None'

                    signatures[node.name] = {
                        'name': node.name,
                        'parameters': params,
                        'docstring': ast.get_docstring(node) or ''
                    }

        except Exception as e:
            print(f"Warning: Could not parse {file_path}: {e}")

        return signatures

    def load_all_tool_signatures(self):
        """Load signatures from all tool files"""
        tools_dir = Path(__file__).parent.parent.parent / 'server' / 'ai_agents' / 'tools'

        for py_file in tools_dir.glob('*.py'):
            if py_file.name.startswith('_'):
                continue
            signatures = self.parse_tool_file(py_file)
            self.tools_signatures.update(signatures)

    def get_tool_signature(self, tool_name: str) -> Optional[Dict]:
        """Get the signature of a tool function"""
        if not hasattr(self, 'tools_signatures'):
            self.load_all_tool_signatures()

        return self.tools_signatures.get(tool_name)

    def _category_prefix(self, tool_name: str) -> str:
        """Generate category prefix for test ID"""
        category = TOOL_CATEGORIES.get(tool_name, 'misc')
        category_map = {
            'analysis': 'ANL',
            'api_database': 'API',
            'code_understanding': 'COD',
            'data_flow': 'DFL',
            'relationship': 'REL',
            'repository_intelligence': 'REP',
            'security_quality': 'SEC',
            'misc': 'MSC'
        }
        return category_map.get(category, 'MSC')

    def _get_tool_category(self, tool_name: str) -> str:
        """Get the category for a tool"""
        return TOOL_CATEGORIES.get(tool_name, 'misc')

    def _get_description(self, test_type: str, tool_name: str) -> str:
        """Generate description for a test"""
        test_desc = TEST_CATEGORIES.get(test_type, test_type)
        return f"{test_desc} test for {tool_name}"

    def _select_fixture(self, tool_name: str, test_type: str) -> str:
        """Select appropriate fixture for a test"""
        category = self._get_tool_category(tool_name)

        # Default to simple-python for most tests
        if test_type in ['T06', 'T07']:  # Large/Complex input
            return 'polyglot-monorepo'  # Would need to create this
        elif test_type == 'T08':  # Malformed input
            return 'corrupted-inputs'
        else:
            return 'simple-python'

    def _generate_input(self, tool_name: str, test_type: str, signature: Optional[Dict] = None) -> Dict:
        """Generate input for a test based on tool signature"""
        if not signature:
            return {}

        input_data = {}
        category = self._get_tool_category(tool_name)

        for param in signature['parameters']:
            param_name = param['name']

            # Generate appropriate input based on parameter name and category
            if param_name == 'file_path':
                if test_type == 'T08':  # Malformed
                    input_data[param_name] = '/nonexistent/path.py'
                else:
                    input_data[param_name] = 'main.py'
            elif param_name == 'repository_path':
                input_data[param_name] = '/path/to/repo'
            elif param_name == 'symbol':
                input_data[param_name] = 'target'
            elif param_name == 'depth':
                input_data[param_name] = 1 if test_type == 'T01' else 2
            elif param_name == 'query':
                input_data[param_name] = 'test'
            elif param_name == 'schema_path':
                input_data[param_name] = 'openapi.yaml'
            elif param_name == 'schema_type':
                input_data[param_name] = 'openapi'
            elif param_name == 'language':
                input_data[param_name] = 'python'
            elif param_name == 'max_results':
                input_data[param_name] = 10
            elif param_name == 'code':
                input_data[param_name] = 'def test(): return True'
            elif param['required'] and param.get('default') is None:
                # For required params without defaults, provide placeholder
                input_data[param_name] = 'placeholder'

        return input_data

    def _generate_expected(self, tool_name: str, test_type: str) -> Dict:
        """Generate expected output for a test"""
        if test_type in ['T02', 'T04', 'T08', 'T09']:
            # These tests expect errors or empty results
            return {'status': 'error' if test_type in ['T02', 'T08', 'T09'] else 'ok'}
        else:
            # Happy path tests expect success
            return {'status': 'ok'}

    def _generate_must_not(self, tool_name: str, test_type: str) -> List:
        """Generate must_not constraints for a test"""
        if test_type == 'T01':
            # Happy path should not have errors
            return ['error']
        return []

    def _generate_checks(self, tool_name: str, test_type: str) -> List[Dict]:
        """Generate checks for a test"""
        checks = []

        # Basic schema validity check
        checks.append({
            'type': 'schema_validity',
            'required_fields': ['status']
        })

        # Performance check
        if test_type == 'T13':
            category = self._get_tool_category(tool_name)
            perf_target = PERFORMANCE_TARGETS.get(category, PERFORMANCE_TARGETS['default'])
            checks.append({
                'type': 'performance',
                'max_duration_ms': perf_target['max_duration_ms']
            })

        return checks

    def _get_performance_targets(self, tool_name: str) -> Dict:
        """Get performance targets for a tool"""
        category = self._get_tool_category(tool_name)
        return PERFORMANCE_TARGETS.get(category, PERFORMANCE_TARGETS['default'])

    def _get_severity(self, tool_name: str, test_type: str) -> str:
        """Get severity for a test"""
        return SEVERITY_BY_CATEGORY.get(test_type, 'medium')

    def create_spec(self, tool_name: str, test_type: str, signature: Optional[Dict] = None) -> Dict:
        """Create a single test specification"""
        test_id = f"{self._category_prefix(tool_name)}-{tool_name}-{test_type}"

        return {
            'test_id': test_id,
            'name': f"{TEST_CATEGORIES.get(test_type, test_type)} test for {tool_name}",
            'category': self._get_tool_category(tool_name),
            'tool': tool_name,
            'layer': 1 if test_type.startswith('T0') else 2,
            'test_type': test_type,
            'description': self._get_description(test_type, tool_name),
            'fixture': self._select_fixture(tool_name, test_type),
            'input': self._generate_input(tool_name, test_type, signature),
            'expected': self._generate_expected(tool_name, test_type),
            'must_not': self._generate_must_not(tool_name, test_type),
            'checks': self._generate_checks(tool_name, test_type),
            'performance': self._get_performance_targets(tool_name),
            'severity': self._get_severity(tool_name, test_type)
        }

    def generate_for_tool(self, tool_name: str, test_types: Optional[List[str]] = None) -> List[Dict]:
        """Generate test specs for a single tool"""
        if test_types is None:
            test_types = list(TEST_CATEGORIES.keys())

        # Get tool signature
        signature = self.get_tool_signature(tool_name)

        specs = []
        for test_type in test_types:
            spec = self.create_spec(tool_name, test_type, signature)
            specs.append(spec)

        return specs

    def generate_for_tools(self, tool_names: List[str], test_types: Optional[List[str]] = None) -> Dict[str, List[Dict]]:
        """Generate test specs for multiple tools"""
        results = {}
        for tool_name in tool_names:
            results[tool_name] = self.generate_for_tool(tool_name, test_types)
        return results

    def save_spec(self, spec: Dict, output_dir: Path):
        """Save a single test spec to YAML file"""
        category = spec['category']
        layer = spec['layer']

        # Create directory structure: tests/layer{N}/{category}/
        dir_path = output_dir / f'layer{layer}' / category
        dir_path.mkdir(parents=True, exist_ok=True)

        # Save to file
        file_path = dir_path / f"{spec['test_id']}.yaml"
        with open(file_path, 'w') as f:
            yaml.dump(spec, f, default_flow_style=False, sort_keys=False)

        return file_path

    def save_specs(self, specs: List[Dict], output_dir: Path):
        """Save multiple test specs to YAML files"""
        saved_paths = []
        for spec in specs:
            path = self.save_spec(spec, output_dir)
            saved_paths.append(path)
        return saved_paths


def main():
    """Main entry point for test spec generation"""
    import argparse

    parser = argparse.ArgumentParser(description='Generate test specifications for JARVIS tools')
    parser.add_argument('--tool', type=str, help='Generate specs for a specific tool')
    parser.add_argument('--tools', type=str, nargs='+', help='Generate specs for multiple tools')
    parser.add_argument('--test-types', type=str, nargs='+', help='Test types to generate (T01-T15)')
    parser.add_argument('--layer1', action='store_true', help='Generate Layer 1 tests (T01-T09)')
    parser.add_argument('--layer2', action='store_true', help='Generate Layer 2 tests (T10-T15)')
    parser.add_argument('--output', type=str, default='tests', help='Output directory')

    args = parser.parse_args()

    # Determine test types
    if args.test_types:
        test_types = args.test_types
    elif args.layer1:
        test_types = [f'T0{i}' for i in range(1, 10)]
    elif args.layer2:
        test_types = [f'T1{i}' for i in range(0, 6)]
    else:
        test_types = list(TEST_CATEGORIES.keys())

    # Initialize generator
    test_root = Path(__file__).parent.parent
    generator = TestSpecGenerator(test_root)
    generator.load_tools_module()

    # Determine tools
    if args.tool:
        tool_names = [args.tool]
    elif args.tools:
        tool_names = args.tools
    else:
        # Generate for all untested tools
        tool_names = list(TOOL_CATEGORIES.keys())

    # Generate specs
    output_dir = test_root / args.output
    total_saved = 0

    for tool_name in tool_names:
        print(f"Generating specs for {tool_name}...")
        specs = generator.generate_for_tool(tool_name, test_types)
        saved = generator.save_specs(specs, output_dir)
        total_saved += len(saved)
        print(f"  Saved {len(saved)} specs")

    print(f"\nTotal specs generated: {total_saved}")
    print(f"Output directory: {output_dir}")


if __name__ == '__main__':
    main()
