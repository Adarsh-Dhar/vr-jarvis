#!/usr/bin/env python3
"""
Spec Conversion Script
Converts generated placeholder specs to real expected answers
"""

import sys
import yaml
import inspect
from pathlib import Path
from typing import Dict, List, Any, Optional
import json

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'server'))
sys.path.insert(0, str(Path(__file__).parent))

from test_registry import TestRegistry


class SpecConverter:
    """Converts placeholder test specs to real expected answers"""

    def __init__(self, test_root: Path):
        self.test_root = test_root
        self.registry = TestRegistry(test_root)
        self.registry.load_test_definitions()

        # Import tools module
        from ai_agents import tools
        self.tools = tools

        # Fixture mapping
        self.fixture_mapping = {
            'simple-python': {
                'path': test_root / 'fixtures' / 'repositories' / 'simple-python',
                'description': 'Simple Python repository with multiple functions and classes'
            },
            'complex-typescript': {
                'path': test_root / 'fixtures' / 'repositories' / 'complex-typescript',
                'description': 'Complex TypeScript project with type definitions'
            },
            'cpp-project': {
                'path': test_root / 'fixtures' / 'repositories' / 'cpp-project',
                'description': 'C++ project with templates and classes'
            },
            'rust-project': {
                'path': test_root / 'fixtures' / 'repositories' / 'rust-project',
                'description': 'Rust project with ownership patterns'
            },
            'polyglot-monorepo': {
                'path': test_root / 'fixtures' / 'repositories' / 'polyglot-monorepo',
                'description': 'Multi-language monorepo'
            },
            'spring-boot': {
                'path': test_root / 'fixtures' / 'repositories' / 'spring-boot',
                'description': 'Java Spring Boot application'
            },
            'security-challenge': {
                'path': test_root / 'fixtures' / 'repositories' / 'security-challenge',
                'description': 'Repository with security vulnerabilities'
            }
        }

    def get_tool_signature(self, tool_name: str) -> inspect.Signature:
        """Get the signature of a tool function"""
        tool_func = getattr(self.tools, tool_name, None)
        if not tool_func:
            return None
        return inspect.signature(tool_func)

    def get_tool_parameters(self, tool_name: str) -> List[str]:
        """Get parameter names from tool signature"""
        sig = self.get_tool_signature(tool_name)
        if not sig:
            return []
        return [p.name for p in sig.parameters.values() if p.name != 'tool_context']

    def generate_test_input(self, tool_name: str, fixture: str) -> Dict[str, Any]:
        """Generate realistic test input for a tool based on fixture"""
        params = self.get_tool_parameters(tool_name)
        input_data = {}

        fixture_path = self.fixture_mapping.get(fixture, {}).get('path')
        if not fixture_path:
            return input_data

        # Generate inputs based on parameter names
        for param in params:
            if 'file_path' in param:
                input_data[param] = f'fixtures/repositories/{fixture}/main.py'
            elif 'path' in param:
                input_data[param] = f'fixtures/repositories/{fixture}'
            elif 'directory' in param:
                input_data[param] = f'fixtures/repositories/{fixture}'
            elif 'repository' in param:
                input_data[param] = f'fixtures/repositories/{fixture}'
            elif 'query' in param or 'search' in param:
                input_data[param] = 'target'
            elif 'symbol' in param:
                input_data[param] = 'target'
            elif 'function' in param:
                input_data[param] = 'target'
            elif 'language' in param:
                input_data[param] = 'python'
            elif 'content' in param:
                input_data[param] = 'test content'
            elif 'line' in param:
                input_data[param] = 1
            elif 'start' in param:
                input_data[param] = 1
            elif 'end' in param:
                input_data[param] = 10
            else:
                # Default placeholder
                input_data[param] = 'placeholder'

        return input_data

    def run_tool_and_capture_output(self, tool_name: str, input_data: Dict[str, Any]) -> Optional[Dict]:
        """Run a tool with input and capture its output"""
        tool_func = getattr(self.tools, tool_name, None)
        if not tool_func:
            return None

        # Create mock ToolContext
        class MockToolContext:
            def __init__(self):
                self.state = {}

        tool_context = MockToolContext()

        # Make paths absolute
        input_copy = input_data.copy()
        for key, value in input_copy.items():
            if isinstance(value, str) and 'fixtures/repositories' in value:
                input_copy[key] = str(self.test_root / value)

        try:
            output = tool_func(**input_copy, tool_context=tool_context)
            return output
        except Exception as e:
            print(f"Error running tool {tool_name}: {e}")
            return None

    def generate_expected_output(self, tool_name: str, output: Dict) -> Dict[str, Any]:
        """Generate expected output section from actual tool output"""
        expected = {}

        if not output:
            return expected

        # Always include status
        if 'status' in output:
            expected['status'] = output['status']

        # For successful outputs, include key fields
        if output.get('status') == 'ok':
            # Include file-related fields
            if 'file_path' in output:
                expected['file_path_contains'] = Path(output['file_path']).name

            # Include content hints
            if 'content' in output and output['content']:
                content_str = str(output['content'])
                # Find first function/class name as content hint
                if 'def ' in content_str:
                    import re
                    match = re.search(r'def (\w+)', content_str)
                    if match:
                        expected['content_contains'] = [f'def {match.group(1)}']
                elif 'class ' in content_str:
                    import re
                    match = re.search(r'class (\w+)', content_str)
                    if match:
                        expected['content_contains'] = [f'class {match.group(1)}']

            # Include line count for file operations
            if 'content' in output:
                lines = output['content'].split('\n') if output['content'] else []
                expected['line_count'] = len(lines)

            # Include language for parsing tools
            if 'language' in output:
                expected['language'] = output['language']

            # Include AST not empty for AST tools
            if 'ast' in output:
                expected['ast_not_empty'] = True

            # Include symbol hints for symbol tools
            if 'symbols' in output and output['symbols']:
                if isinstance(output['symbols'], list) and len(output['symbols']) > 0:
                    first_symbol = output['symbols'][0]
                    if isinstance(first_symbol, dict) and 'name' in first_symbol:
                        expected['symbol_contains'] = first_symbol['name']

        return expected

    def generate_must_not_checks(self, tool_name: str, output: Dict) -> List:
        """Generate must_not checks"""
        must_not = []

        # Always forbid error status
        must_not.append('error')

        # Forbid empty critical fields
        if output.get('status') == 'ok':
            if 'content' in output:
                must_not.append({'content': ''})
            if 'symbols' in output:
                must_not.append({'symbols': []})

        return must_not

    def generate_checks(self, tool_name: str, output: Dict) -> List[Dict]:
        """Generate validation checks"""
        checks = []

        # Always include schema validity
        required_fields = ['status']
        if output.get('status') == 'ok':
            if 'file_path' in output:
                required_fields.append('file_path')
            if 'content' in output:
                required_fields.append('content')
            if 'ast' in output:
                required_fields.append('ast')
            if 'symbols' in output:
                required_fields.append('symbols')

        checks.append({
            'type': 'schema_validity',
            'required_fields': required_fields
        })

        # Add content validation if content exists
        if output.get('content'):
            checks.append({
                'type': 'content_validation',
                'required_content': []
            })

        # Add non-empty check for critical fields
        non_empty_fields = []
        if output.get('content'):
            non_empty_fields.append('content')
        if output.get('ast'):
            non_empty_fields.append('ast')
        if output.get('symbols'):
            non_empty_fields.append('symbols')

        if non_empty_fields:
            checks.append({
                'type': 'non_empty_check',
                'fields': non_empty_fields
            })

        return checks

    def convert_spec(self, test_id: str) -> Optional[Dict]:
        """Convert a single test spec to real expected answers"""
        test_def = self.registry.get_test(test_id)
        if not test_def:
            print(f"Test not found: {test_id}")
            return None

        tool_name = test_def.get('tool')
        if not tool_name:
            print(f"No tool specified in test: {test_id}")
            return None

        fixture = test_def.get('fixture', 'simple-python')

        print(f"Converting {test_id} (tool: {tool_name}, fixture: {fixture})")

        # Generate test input
        input_data = self.generate_test_input(tool_name, fixture)
        print(f"  Generated input: {input_data}")

        # Run tool and capture output
        output = self.run_tool_and_capture_output(tool_name, input_data)
        if not output:
            print(f"  Failed to run tool {tool_name}")
            return None

        print(f"  Tool output status: {output.get('status')}")

        # Generate expected output
        expected = self.generate_expected_output(tool_name, output)
        print(f"  Generated expected: {expected}")

        # Generate must_not checks
        must_not = self.generate_must_not_checks(tool_name, output)

        # Generate validation checks
        checks = self.generate_checks(tool_name, output)

        # Update test definition
        test_def['input'] = input_data
        test_def['expected'] = expected
        test_def['must_not'] = must_not
        test_def['checks'] = checks

        return test_def

    def convert_all_specs_for_tool(self, tool_name: str) -> List[str]:
        """Convert all specs for a specific tool"""
        test_ids = self.registry.get_tests_by_tool(tool_name)
        converted = []

        for test_id in test_ids:
            converted_spec = self.convert_spec(test_id)
            if converted_spec:
                # Save the converted spec
                test_def = self.registry.get_test(test_id)
                if test_def and 'file' in test_def:
                    # This is a Python test, skip
                    continue

                # Find the YAML file path
                for yaml_file in self.test_root.rglob('*.yaml'):
                    try:
                        with open(yaml_file, 'r') as f:
                            existing = yaml.safe_load(f)
                            if existing and existing.get('test_id') == test_id:
                                # Write the converted spec
                                with open(yaml_file, 'w') as f:
                                    yaml.dump(converted_spec, f, default_flow_style=False, sort_keys=False)
                                print(f"  Saved: {yaml_file}")
                                converted.append(test_id)
                                break
                    except Exception as e:
                        print(f"  Error processing {yaml_file}: {e}")

        return converted

    def convert_all_specs(self) -> Dict[str, List[str]]:
        """Convert all test specs"""
        results = {}

        # Get all unique tools
        all_tools = set()
        for test_def in self.registry.get_all_tests().values():
            tool = test_def.get('tool')
            if tool:
                all_tools.add(tool)

        print(f"Found {len(all_tools)} unique tools to convert")

        for tool_name in sorted(all_tools):
            print(f"\n=== Converting specs for {tool_name} ===")
            converted = self.convert_all_specs_for_tool(tool_name)
            results[tool_name] = converted
            print(f"Converted {len(converted)} specs for {tool_name}")

        return results


def main():
    """Main entry point"""
    test_root = Path('/Users/adarsh/Documents/vr-agent/jarvis-tests')
    converter = SpecConverter(test_root)

    # Convert all specs
    results = converter.convert_all_specs()

    # Print summary
    print("\n=== Conversion Summary ===")
    total_converted = sum(len(v) for v in results.values())
    print(f"Total specs converted: {total_converted}")
    for tool_name, converted in results.items():
        print(f"  {tool_name}: {len(converted)}")


if __name__ == '__main__':
    main()
