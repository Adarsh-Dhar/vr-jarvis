#!/usr/bin/env python3
"""
Map each tool to its expected input fields and fixture data sources
"""

# Tool field mapping based on tool signatures
TOOL_FIELD_MAPPING = {
    # Repository tools
    'read_file': {
        'fields': ['file_path'],
        'source': 'fixture_files',
        'default_fixture': 'simple-python',
        'default_value': 'fixtures/repositories/simple-python/main.py'
    },
    'read_file_range': {
        'fields': ['file_path', 'start_line', 'end_line'],
        'source': 'fixture_files',
        'default_fixture': 'simple-python',
        'default_value': 'fixtures/repositories/simple-python/main.py',
        'extra_values': {'start_line': 1, 'end_line': 10}
    },
    'list_files': {
        'fields': ['directory', 'recursive', 'pattern'],
        'source': 'fixture_directories',
        'default_fixture': 'simple-python',
        'default_value': 'fixtures/repositories/simple-python',
        'extra_values': {'recursive': True, 'pattern': None}
    },
    'search_files': {
        'fields': ['pattern', 'directory', 'file_extension'],
        'source': 'fixture_directories',
        'default_fixture': 'simple-python',
        'default_value': 'fixtures/repositories/simple-python',
        'extra_values': {'pattern': '*.py', 'file_extension': '.py'}
    },
    'search_code': {
        'fields': ['query', 'directory', 'file_pattern'],
        'source': 'fixture_directories',
        'default_fixture': 'simple-python',
        'default_value': 'fixtures/repositories/simple-python',
        'extra_values': {'query': 'def', 'file_pattern': '*.py'}
    },

    # Code understanding tools
    'parse_source_code': {
        'fields': ['file_path'],
        'source': 'fixture_files',
        'default_fixture': 'simple-python',
        'default_value': 'fixtures/repositories/simple-python/main.py'
    },
    'explain_function': {
        'fields': ['function_id'],
        'source': 'fixture_functions',
        'default_fixture': 'simple-python',
        'default_value': 'alpha'
    },
    'explain_class': {
        'fields': ['class_id'],
        'source': 'fixture_classes',
        'default_fixture': 'simple-python',
        'default_value': 'ExampleClass'
    },
    'explain_module': {
        'fields': ['file_path'],
        'source': 'fixture_files',
        'default_fixture': 'simple-python',
        'default_value': 'fixtures/repositories/simple-python/main.py'
    },

    # Relationship tools
    'find_callers': {
        'fields': ['function_id'],
        'source': 'fixture_functions',
        'default_fixture': 'simple-python',
        'default_value': 'alpha'
    },
    'find_callees': {
        'fields': ['function_id'],
        'source': 'fixture_functions',
        'default_fixture': 'simple-python',
        'default_value': 'alpha'
    },
    'find_indirect_callers': {
        'fields': ['function_id'],
        'source': 'fixture_functions',
        'default_fixture': 'simple-python',
        'default_value': 'alpha'
    },
    'build_call_graph': {
        'fields': ['file_path'],
        'source': 'fixture_files',
        'default_fixture': 'simple-python',
        'default_value': 'fixtures/repositories/simple-python/main.py'
    },
    'build_dependency_graph': {
        'fields': ['directory'],
        'source': 'fixture_directories',
        'default_fixture': 'simple-python',
        'default_value': 'fixtures/repositories/simple-python'
    },

    # Common patterns for unmapped tools
    'default': {
        'fields': ['file_path', 'function_id', 'directory', 'pattern', 'query'],
        'source': 'fixture_files',
        'default_fixture': 'simple-python',
        'default_value': 'fixtures/repositories/simple-python/main.py'
    }
}

# Fixture data cache
FIXTURE_DATA = {
    'simple-python': {
        'files': [
            'fixtures/repositories/simple-python/main.py',
            'fixtures/repositories/simple-python/subpackage/helper.py',
            'fixtures/repositories/simple-python/subpackage/__init__.py'
        ],
        'directories': [
            'fixtures/repositories/simple-python',
            'fixtures/repositories/simple-python/subpackage'
        ],
        'functions': ['alpha', 'beta', 'gamma', 'delta', 'target', 'epsilon'],
        'classes': ['ExampleClass']
    },
    'complex-typescript': {
        'files': ['fixtures/repositories/complex-typescript/src/index.ts'],
        'directories': ['fixtures/repositories/complex-typescript'],
        'functions': [],
        'classes': []
    },
    'spring-boot': {
        'files': ['fixtures/repositories/spring-boot/src/main/java/Application.java'],
        'directories': ['fixtures/repositories/spring-boot'],
        'functions': [],
        'classes': []
    }
}

def get_tool_mapping(tool_name):
    """Get mapping for a tool"""
    return TOOL_FIELD_MAPPING.get(tool_name, TOOL_FIELD_MAPPING['default'])

def get_fixture_value(fixture_name, field_type):
    """Get a value from fixture data"""
    fixture = FIXTURE_DATA.get(fixture_name, FIXTURE_DATA['simple-python'])

    if field_type == 'file_path':
        return fixture['files'][0] if fixture['files'] else 'fixtures/repositories/simple-python/main.py'
    elif field_type == 'directory':
        return fixture['directories'][0] if fixture['directories'] else 'fixtures/repositories/simple-python'
    elif field_type == 'function_id':
        return fixture['functions'][0] if fixture['functions'] else 'alpha'
    elif field_type == 'class_id':
        return fixture['classes'][0] if fixture['classes'] else 'ExampleClass'
    elif field_type == 'pattern':
        return '*.py'
    elif field_type == 'query':
        return 'def'
    else:
        return 'fixtures/repositories/simple-python/main.py'

if __name__ == '__main__':
    print("Tool Field Mapping:")
    print("=" * 60)
    for tool, mapping in TOOL_FIELD_MAPPING.items():
        if tool != 'default':
            print(f"{tool}:")
            print(f"  Fields: {mapping['fields']}")
            print(f"  Source: {mapping['source']}")
            print(f"  Default: {mapping['default_value']}")
