"""
Agent 6 - Data Flow Intelligence Tools
Understand how data moves through the entire application.
"""

from typing import Optional, List, Dict, Any
from google.adk.tools import ToolContext
from ._safe import safe


@safe
def trace_variable_origin(variable_id: str, tool_context: ToolContext) -> dict:
    """Find where a variable's value originates."""
    try:
        from .navigation_tools import get_symbol_definition
        from .repository_tools import search_code
        
        # Find definition
        def_result = get_symbol_definition(variable_id, tool_context)
        
        if def_result.get('status') == 'ok':
            definition = def_result['definition']
            return {
                'status': 'ok',
                'variable_id': variable_id,
                'origin': {
                    'file': definition.get('file'),
                    'line': definition.get('line'),
                    'type': definition.get('symbol_type')
                }
            }
        
        # Fallback to code search
        search_result = search_code(tool_context, query=f'{variable_id} =')
        if search_result.get('status') == 'ok' and search_result.get('matches'):
            first_match = search_result['matches'][0]
            return {
                'status': 'ok',
                'variable_id': variable_id,
                'origin': {
                    'file': first_match.get('file'),
                    'line': first_match.get('line'),
                    'snippet': first_match.get('snippet')
                }
            }
        
        return {
            'status': 'not_found',
            'variable_id': variable_id,
            'message': 'Variable origin not found'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_variable_usage(variable_id: str, tool_context: ToolContext) -> dict:
    """Find where it is used."""
    try:
        from .navigation_tools import get_symbol_references
        return get_symbol_references(variable_id, tool_context)
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_variable_modifications(
    variable_id: str,
    tool_context: ToolContext
) -> dict:
    """Track where a variable is modified."""
    try:
        from .navigation_tools import get_symbol_references
        return get_symbol_references(variable_id, tool_context)
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_parameter_flow(
    function_id: str,
    parameter: str,
    tool_context: ToolContext
) -> dict:
    """Track how a parameter flows through a function."""
    try:
        from .navigation_tools import get_symbol_definition
        from .repository_tools import read_file
        
        # Get function definition
        def_result = get_symbol_definition(function_id, tool_context)
        if def_result.get('status') != 'ok':
            return def_result
        
        file_path = def_result['definition']['file']
        line_num = def_result['definition']['line']
        
        # Read file and analyze parameter usage
        file_result = read_file(file_path, tool_context)
        if file_result.get('status') != 'ok':
            return file_result
        
        content = file_result['content']
        lines = content.splitlines()
        
        # Find parameter usage within function
        usages = []
        in_function = False
        function_indent = 0
        
        for i, line in enumerate(lines, 1):
            if i == line_num:
                in_function = True
                function_indent = len(line) - len(line.lstrip())
                continue
            
            if in_function:
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= function_indent and line.strip():
                    # End of function
                    break
                
                if parameter in line:
                    usages.append({
                        'line': i,
                        'snippet': line.strip()
                    })
        
        return {
            'status': 'ok',
            'function_id': function_id,
            'parameter': parameter,
            'usages': usages,
            'usage_count': len(usages)
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_return_value_flow(
    function_id: str,
    tool_context: ToolContext
) -> dict:
    """Track where return values flow."""
    try:
        from .navigation_tools import get_symbol_references, get_symbol_definition
        
        # Find all references to the function (call sites)
        ref_result = get_symbol_references(function_id, tool_context)
        
        if ref_result.get('status') != 'ok':
            return ref_result
        
        # Filter for function calls
        call_sites = [ref for ref in ref_result['references'] if ref.get('type') == 'call']
        
        return {
            'status': 'ok',
            'function_id': function_id,
            'return_flow': {
                'call_sites': call_sites,
                'call_count': len(call_sites)
            }
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_taint_flow(
    source: str,
    tool_context: ToolContext
) -> dict:
    """Track tainted data (security analysis)."""
    try:
        from .repository_tools import search_code
        
        # Search for common taint sources (user input, environment variables, etc.)
        taint_patterns = [
            'request.get',
            'request.POST',
            'request.GET',
            'os.environ',
            'input(',
            'sys.argv',
            'raw_input',
            'eval(',
            'exec('
        ]
        
        tainted_variables = []
        for pattern in taint_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    tainted_variables.append({
                        'source': pattern,
                        'file': match['file'],
                        'line': match['line'],
                        'snippet': match['snippet']
                    })
        
        return {
            'status': 'ok',
            'source': source,
            'tainted_sources': tainted_variables,
            'note': 'Basic taint analysis - full analysis requires runtime instrumentation'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_transformations(
    variable_id: str,
    tool_context: ToolContext
) -> dict:
    """Track data transformations."""
    try:
        from .repository_tools import search_code
        
        # Search for common transformation patterns
        transformation_patterns = [
            f'{variable_id}.lower()',
            f'{variable_id}.upper()',
            f'{variable_id}.strip()',
            f'{variable_id}.replace(',
            f'{variable_id}.split(',
            f'{variable_id}.join(',
            f'{variable_id}.encode(',
            f'{variable_id}.decode(',
            f'{variable_id}.format(',
            f'int({variable_id})',
            f'str({variable_id})',
            f'float({variable_id})'
        ]
        
        transformations = []
        for pattern in transformation_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    transformations.append({
                        'transformation': pattern,
                        'file': match['file'],
                        'line': match['line'],
                        'snippet': match['snippet']
                    })
        
        return {
            'status': 'ok',
            'variable_id': variable_id,
            'transformations': transformations
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_cross_function_flow(
    variable_id: str,
    tool_context: ToolContext
) -> dict:
    """Track data across function boundaries."""
    try:
        from .navigation_tools import get_symbol_references
        from .repository_tools import search_code
        
        # Find all references to the variable
        ref_result = get_symbol_references(variable_id, tool_context)
        
        if ref_result.get('status') != 'ok':
            return ref_result
        
        # Analyze references to find function boundaries
        cross_function_flows = []
        for ref in ref_result['references']:
            # Search for function definitions near the reference
            search_result = search_code(tool_context, query='def ')
            if search_result.get('status') == 'ok':
                cross_function_flows.append({
                    'variable_id': variable_id,
                    'file': ref['file'],
                    'line': ref['line'],
                    'type': ref.get('type', 'unknown')
                })
        
        return {
            'status': 'ok',
            'variable_id': variable_id,
            'cross_function_flows': cross_function_flows,
            'note': 'Simplified analysis - full cross-function flow requires AST analysis'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_cross_service_flow(
    data_id: str,
    tool_context: ToolContext
) -> dict:
    """Track data across service boundaries."""
    try:
        from .repository_tools import search_code
        
        # Search for cross-service patterns
        service_patterns = [
            'requests.get',
            'requests.post',
            'http.request',
            'fetch(',
            'axios.',
            'grpc.',
            'redis.',
            'kafka.',
            'rabbitmq.',
            'sqs.',
            'publish(',
            'emit('
        ]
        
        service_calls = []
        for pattern in service_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    service_calls.append({
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line'],
                        'snippet': match['snippet']
                    })
        
        return {
            'status': 'ok',
            'data_id': data_id,
            'service_calls': service_calls,
            'count': len(service_calls),
            'note': 'Pattern-based analysis - full cross-service flow requires runtime tracing'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_database_reads(
    query_id: str,
    tool_context: ToolContext
) -> dict:
    """Track data from database reads."""
    try:
        from .repository_tools import search_code
        
        # Search for database read patterns
        read_patterns = [
            'SELECT',
            '.find(',
            '.get(',
            '.filter(',
            '.all()',
            '.first()',
            '.one()',
            'select(',
            'query('
        ]
        
        read_operations = []
        for pattern in read_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    read_operations.append({
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line'],
                        'snippet': match['snippet']
                    })
        
        return {
            'status': 'ok',
            'query_id': query_id,
            'read_operations': read_operations,
            'count': len(read_operations),
            'note': 'Pattern-based analysis - full database read tracking requires runtime tracing'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_database_writes(
    query_id: str,
    tool_context: ToolContext
) -> dict:
    """Track data to database writes."""
    try:
        from .repository_tools import search_code
        
        # Search for database write patterns
        write_patterns = [
            'INSERT',
            'UPDATE',
            'DELETE',
            '.save(',
            '.create(',
            '.update(',
            '.delete(',
            '.add(',
            '.remove(',
            'insert(',
            'update(',
            'delete('
        ]
        
        write_operations = []
        for pattern in write_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    write_operations.append({
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line'],
                        'snippet': match['snippet']
                    })
        
        return {
            'status': 'ok',
            'query_id': query_id,
            'write_operations': write_operations,
            'count': len(write_operations),
            'note': 'Pattern-based analysis - full database write tracking requires runtime tracing'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_api_data_flow(
    endpoint: str,
    tool_context: ToolContext
) -> dict:
    """Track data through API calls."""
    try:
        from .repository_tools import search_code
        
        # Search for API data flow patterns
        api_patterns = [
            'request.json',
            'request.data',
            'request.form',
            'request.body',
            'response.json',
            'json.dumps',
            'json.loads',
            '@app.route',
            '@api.route',
            'POST',
            'PUT',
            'PATCH'
        ]
        
        api_flows = []
        for pattern in api_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    api_flows.append({
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line'],
                        'snippet': match['snippet']
                    })
        
        return {
            'status': 'ok',
            'endpoint': endpoint,
            'api_flows': api_flows,
            'count': len(api_flows),
            'note': 'Pattern-based analysis - full API data flow tracking requires runtime tracing'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_file_operations(
    file_path: str,
    tool_context: ToolContext
) -> dict:
    """Track data through file operations."""
    try:
        from .repository_tools import search_code
        
        # Search for file operation patterns
        file_patterns = [
            'open(',
            '.read(',
            '.write(',
            '.readlines(',
            '.writelines(',
            'with open',
            'Path(',
            'read_file',
            'write_file',
            'save(',
            'load('
        ]
        
        file_ops = []
        for pattern in file_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    file_ops.append({
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line'],
                        'snippet': match['snippet']
                    })
        
        return {
            'status': 'ok',
            'file_path': file_path,
            'file_operations': file_ops,
            'count': len(file_ops),
            'note': 'Pattern-based analysis - full file operation tracking requires runtime tracing'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_state_changes(
    component_id: str,
    tool_context: ToolContext
) -> dict:
    """Track state mutations."""
    try:
        from .repository_tools import search_code
        
        # Search for state change patterns
        state_patterns = [
            'setState',
            'useState',
            'this.state',
            '.state =',
            'self.',
            'state.',
            'dispatch(',
            'emit(',
            'store.',
            'setState('
        ]
        
        state_changes = []
        for pattern in state_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    state_changes.append({
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line'],
                        'snippet': match['snippet']
                    })
        
        return {
            'status': 'ok',
            'component_id': component_id,
            'state_changes': state_changes,
            'count': len(state_changes),
            'note': 'Pattern-based analysis - full state change tracking requires runtime tracing'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def build_data_flow_graph(
    scope: str,
    tool_context: ToolContext
) -> dict:
    """Build data flow graphs."""
    try:
        from .analysis_tools import analyze_data_flow
        return analyze_data_flow(scope, tool_context)
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def identify_data_sinks(variable_id: str, tool_context: ToolContext) -> dict:
    """Identify where data ends up (database, API, file, etc.)."""
    try:
        from .repository_tools import search_code
        
        # Search for common data sink patterns
        sink_patterns = [
            f'{variable_id}.write(',
            f'{variable_id}.execute(',
            f'{variable_id}.save(',
            f'cursor.execute({variable_id}',
            f'print({variable_id}',
            f'log({variable_id}',
            f'return {variable_id}',
            f'response.write({variable_id}'
        ]
        
        sinks = []
        for pattern in sink_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    # Infer sink type from pattern
                    sink_type = 'unknown'
                    if 'write' in pattern or 'save' in pattern:
                        sink_type = 'file/database'
                    elif 'execute' in pattern:
                        sink_type = 'database'
                    elif 'print' in pattern or 'log' in pattern:
                        sink_type = 'output/log'
                    elif 'return' in pattern:
                        sink_type = 'function_return'
                    elif 'response' in pattern:
                        sink_type = 'api_response'
                    
                    sinks.append({
                        'variable_id': variable_id,
                        'sink_type': sink_type,
                        'file': match['file'],
                        'line': match['line'],
                        'snippet': match['snippet']
                    })
        
        return {
            'status': 'ok',
            'variable_id': variable_id,
            'data_sinks': sinks
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def identify_data_sources(variable_id: str, tool_context: ToolContext) -> dict:
    """Identify where data comes from (user input, database, API, etc.)."""
    try:
        from .repository_tools import search_code
        
        # Search for assignment patterns to identify sources
        source_patterns = [
            f'{variable_id} = request',
            f'{variable_id} = input(',
            f'{variable_id} = open(',
            f'{variable_id} = cursor.execute',
            f'{variable_id} = requests',
            f'{variable_id} = os.environ',
            f'{variable_id} = sys.argv',
            f'{variable_id} = config',
            f'{variable_id} = settings'
        ]
        
        sources = []
        for pattern in source_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    # Infer source type from pattern
                    source_type = 'unknown'
                    if 'request' in pattern:
                        source_type = 'user_input/api'
                    elif 'input' in pattern:
                        source_type = 'user_input'
                    elif 'open' in pattern:
                        source_type = 'file'
                    elif 'cursor' in pattern or 'execute' in pattern:
                        source_type = 'database'
                    elif 'requests' in pattern:
                        source_type = 'api'
                    elif 'environ' in pattern or 'argv' in pattern:
                        source_type = 'environment'
                    elif 'config' in pattern or 'settings' in pattern:
                        source_type = 'configuration'
                    
                    sources.append({
                        'variable_id': variable_id,
                        'source_type': source_type,
                        'file': match['file'],
                        'line': match['line'],
                        'snippet': match['snippet']
                    })
        
        return {
            'status': 'ok',
            'variable_id': variable_id,
            'data_sources': sources
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def identify_data_leaks(
    data_id: str,
    tool_context: ToolContext
) -> dict:
    """Identify potential data exposure."""
    try:
        from .repository_tools import search_code
        
        # Search for potential data leak patterns
        leak_patterns = [
            f'print({data_id}',
            f'log({data_id}',
            f'logger.{data_id}',
            f'console.log({data_id}',
            f'console.error({data_id}',
            f'response.write({data_id}',
            f'return {data_id}',  # Could leak to API
            f'json.dumps({data_id}',
            f'str({data_id}'  # String conversion might expose
        ]
        
        potential_leaks = []
        for pattern in leak_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    leak_risk = 'medium'
                    if 'console' in pattern or 'print' in pattern:
                        leak_risk = 'high'
                    elif 'log' in pattern:
                        leak_risk = 'high'
                    elif 'response' in pattern:
                        leak_risk = 'high'
                    
                    potential_leaks.append({
                        'data_id': data_id,
                        'leak_type': pattern,
                        'risk': leak_risk,
                        'file': match['file'],
                        'line': match['line'],
                        'snippet': match['snippet']
                    })
        
        return {
            'status': 'ok',
            'data_id': data_id,
            'potential_leaks': potential_leaks,
            'note': 'Static analysis - runtime behavior may differ'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def identify_validation_gaps(
    data_id: str,
    tool_context: ToolContext
) -> dict:
    """Identify missing input validation."""
    try:
        from .repository_tools import search_code
        from .navigation_tools import get_symbol_definition
        
        # Find where data_id is defined
        def_result = get_symbol_definition(data_id, tool_context)
        
        if def_result.get('status') != 'ok':
            return {
                'status': 'not_found',
                'data_id': data_id,
                'message': 'Could not find data definition'
            }
        
        file_path = def_result['definition']['file']
        line_num = def_result['definition']['line']
        
        # Search for validation patterns near the definition
        validation_patterns = [
            'validate',
            'sanitize',
            'clean',
            'strip',
            'escape',
            'check',
            'verify',
            'if.*len(',
            'if not ',
            'if isinstance(',
            'raise ValueError',
            'assert '
        ]
        
        has_validation = False
        validation_found = []
        
        for pattern in validation_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    # Check if validation is near the definition (within 10 lines)
                    if match['file'] == file_path and abs(match['line'] - line_num) <= 10:
                        has_validation = True
                        validation_found.append({
                            'pattern': pattern,
                            'line': match['line'],
                            'snippet': match['snippet']
                        })
        
        return {
            'status': 'ok',
            'data_id': data_id,
            'has_validation': has_validation,
            'validation_found': validation_found,
            'validation_gap': not has_validation,
            'risk': 'high' if not has_validation else 'low'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }
