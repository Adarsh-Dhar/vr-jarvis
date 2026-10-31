#!/usr/bin/env python3
"""
Generate Layer 3 integration tests for tools that need real infrastructure
"""

import sys
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).parent))

# Tools that benefit from integration tests with real infrastructure
INTEGRATION_TEST_TOOLS = {
    # Database tools
    'inspect_database_schema': {
        'fixture': {'type': 'database', 'path': 'integration-test-infrastructure/databases/test.db'},
        'description': 'Inspect SQLite database schema'
    },
    'inspect_tables': {
        'fixture': {'type': 'database', 'path': 'integration-test-infrastructure/databases/test.db'},
        'description': 'Inspect database tables'
    },
    'inspect_columns': {
        'fixture': {'type': 'database', 'path': 'integration-test-infrastructure/databases/test.db'},
        'description': 'Inspect table columns'
    },
    'analyze_database_queries': {
        'fixture': {'type': 'database', 'path': 'integration-test-infrastructure/databases/test.db'},
        'description': 'Analyze database queries'
    },

    # API tools
    'discover_api_endpoints': {
        'fixture': {'type': 'api', 'path': 'integration-test-infrastructure/apis/simple_flask_api.py', 'url': 'http://localhost:5001'},
        'description': 'Discover API endpoints from Flask app'
    },
    'inspect_api_schema': {
        'fixture': {'type': 'api', 'path': 'integration-test-infrastructure/apis/openapi.yaml'},
        'description': 'Inspect OpenAPI schema'
    },
    'inspect_http_routes': {
        'fixture': {'type': 'api', 'path': 'integration-test-infrastructure/apis/simple_flask_api.py'},
        'description': 'Inspect HTTP routes'
    },

    # Git tools
    'get_diff': {
        'fixture': {'type': 'git', 'path': 'integration-test-infrastructure/git-repos/simple-repo'},
        'description': 'Get git diff between branches'
    },
    'trace_file_history': {
        'fixture': {'type': 'git', 'path': 'integration-test-infrastructure/git-repos/simple-repo'},
        'description': 'Trace file history in git'
    },
    'get_branch_info': {
        'fixture': {'type': 'git', 'path': 'integration-test-infrastructure/git-repos/simple-repo'},
        'description': 'Get git branch information'
    },

    # Runtime tools
    'collect_execution_trace': {
        'fixture': {'type': 'runtime', 'path': 'integration-test-infrastructure/runtime/sample_app.py'},
        'description': 'Collect execution trace from running application'
    },
    'record_function_calls': {
        'fixture': {'type': 'runtime', 'path': 'integration-test-infrastructure/runtime/sample_app.py'},
        'description': 'Record function calls during execution'
    },
}


def create_integration_test_spec(tool_name: str, tool_info: dict) -> dict:
    """Create an integration test specification"""
    fixture = tool_info['fixture']
    fixture_type = fixture['type']

    test_id = f"INT-{tool_name.upper()}-001"

    spec = {
        'test_id': test_id,
        'name': f"Integration test for {tool_name}",
        'category': 'integration',
        'tool': tool_name,
        'layer': 3,
        'test_type': 'INTEGRATION',
        'description': tool_info['description'],
        'fixture': fixture,
        'input': _generate_input_for_fixture(fixture_type, tool_name),
        'expected': {
            'status': 'ok'
        },
        'checks': [
            {'type': 'schema_validity', 'required_fields': ['status']},
            {'type': 'integration_connectivity'}
        ],
        'performance': {
            'max_duration_ms': 5000
        },
        'severity': 'high',
        'requires_infrastructure': True
    }

    return spec


def _generate_input_for_fixture(fixture_type: str, tool_name: str) -> dict:
    """Generate appropriate input based on fixture type"""
    if fixture_type == 'database':
        return {
            'database_path': 'integration-test-infrastructure/databases/test.db'
        }
    elif fixture_type == 'api':
        if 'schema' in tool_name:
            return {
                'schema_path': 'integration-test-infrastructure/apis/openapi.yaml',
                'schema_type': 'openapi'
            }
        else:
            return {
                'repository_path': 'integration-test-infrastructure/apis/simple_flask_api.py'
            }
    elif fixture_type == 'git':
        if 'diff' in tool_name:
            return {
                'repository_path': 'integration-test-infrastructure/git-repos/simple-repo',
                'ref1': 'main',
                'ref2': 'feature/new-feature'
            }
        elif 'history' in tool_name:
            return {
                'repository_path': 'integration-test-infrastructure/git-repos/simple-repo',
                'file_path': 'main.py'
            }
        else:
            return {
                'repository_path': 'integration-test-infrastructure/git-repos/simple-repo'
            }
    elif fixture_type == 'runtime':
        return {
            'program_path': 'integration-test-infrastructure/runtime/sample_app.py'
        }
    else:
        return {}


def main():
    test_root = Path(__file__).parent.parent
    output_dir = test_root / 'tests' / 'layer3' / 'integration'

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    total_specs = 0
    failed_tools = []

    for tool_name, tool_info in INTEGRATION_TEST_TOOLS.items():
        print(f"Generating integration test for {tool_name}...")

        try:
            spec = create_integration_test_spec(tool_name, tool_info)

            # Save to YAML file
            file_path = output_dir / f"{spec['test_id']}.yaml"
            with open(file_path, 'w') as f:
                yaml.dump(spec, f, default_flow_style=False, sort_keys=False)

            total_specs += 1
            print(f"  Saved: {file_path.name}")
        except Exception as e:
            import traceback
            print(f"  ERROR: {e}")
            traceback.print_exc()
            failed_tools.append(tool_name)

    print(f"\n{'='*60}")
    print(f"Total integration tests generated: {total_specs}")
    print(f"Failed tools: {len(failed_tools)}")

    if failed_tools:
        print("\nFailed tools:")
        for tool in failed_tools:
            print(f"  - {tool}")

    print(f"\nOutput directory: {output_dir}")


if __name__ == '__main__':
    main()
