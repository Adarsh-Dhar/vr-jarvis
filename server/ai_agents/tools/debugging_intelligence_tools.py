"""
Agent 8 - Debugging Intelligence Tools
Find out why something is broken.
"""

from typing import Optional, List, Dict, Any
import re
import traceback
from google.adk.tools import ToolContext
from ._safe import safe

# In-memory breakpoint state
_breakpoints = {}
_debugger_state = {'active': False, 'current_frame': None}


@safe
def capture_exception(
    application_id: str,
    tool_context: ToolContext
) -> dict:
    """Capture exceptions."""
    try:
        # This would integrate with error tracking (Sentry, etc.)
        # For now, check for exception patterns in logs
        from .repository_tools import search_code
        
        exception_patterns = [
            'Exception',
            'Error',
            'Traceback',
            'raise ',
            'except '
        ]
        
        exceptions_found = []
        for pattern in exception_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches'][:10]:  # Limit to 10 matches
                    exceptions_found.append({
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line'],
                        'snippet': match['snippet']
                    })
        
        return {
            'status': 'ok',
            'application_id': application_id,
            'exceptions_found': exceptions_found,
            'note': 'Static analysis - runtime exception capture requires monitoring integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_stack_trace(stack_trace: str, tool_context: ToolContext) -> dict:
    """Interpret stack traces."""
    try:
        # Parse stack trace
        frames = []
        error_type = 'Unknown'
        error_message = ''
        
        for line in stack_trace.splitlines():
            # Parse Python stack trace format
            if 'Traceback' in line:
                continue
            if line.strip().startswith('File'):
                # Extract file path and line number
                match = re.search(r'File "([^"]+)", line (\d+)', line)
                if match:
                    frames.append({
                        'file': match.group(1),
                        'line': int(match.group(2))
                    })
            elif ':' in line and not line.startswith(' '):
                # Error type and message
                parts = line.split(':', 1)
                if len(parts) == 2:
                    error_type = parts[0].strip()
                    error_message = parts[1].strip()
        
        if frames:
            error_location = frames[-1]
        else:
            error_location = {'file': 'unknown', 'line': 0}
        
        return {
            'status': 'ok',
            'stack_trace': stack_trace,
            'analysis': {
                'error_type': error_type,
                'error_message': error_message,
                'error_location': error_location,
                'frames': frames,
                'depth': len(frames)
            }
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def find_error_origin(
    stack_trace: str,
    tool_context: ToolContext
) -> dict:
    """Identify the likely source of an error."""
    try:
        analysis = analyze_stack_trace(stack_trace, tool_context)
        
        if analysis.get('status') != 'ok':
            return analysis
        
        frames = analysis['analysis'].get('frames', [])
        
        if frames:
            origin = frames[-1]  # The deepest frame is usually the origin
            return {
                'status': 'ok',
                'stack_trace': stack_trace,
                'origin': {
                    'file': origin.get('file', 'unknown'),
                    'line': origin.get('line', 0),
                    'confidence': 0.9
                }
            }
        
        return {
            'status': 'error',
            'error': 'Could not identify error origin from stack trace'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_error_propagation(
    error_id: str,
    tool_context: ToolContext
) -> dict:
    """Follow how errors propagate."""
    try:
        from .repository_tools import search_code
        
        # Search for exception handling patterns
        propagation_patterns = [
            'except ',
            'raise ',
            'finally:',
            'try:'
        ]
        
        propagation_path = []
        for pattern in propagation_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    propagation_path.append({
                        'pattern': pattern,
                        'file': match['file'],
                        'line': match['line'],
                        'snippet': match['snippet']
                    })
        
        return {
            'status': 'ok',
            'error_id': error_id,
            'propagation_path': propagation_path,
            'note': 'Static analysis - runtime propagation requires instrumentation'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def identify_failure_path(
    error_id: str,
    tool_context: ToolContext
) -> dict:
    """Reconstruct the failure path."""
    try:
        from .repository_tools import search_code
        from .navigation_tools import get_symbol_definition
        
        # Try to find the error definition
        def_result = get_symbol_definition(error_id, tool_context)
        
        failure_path = []
        
        if def_result.get('status') == 'ok':
            definition = def_result['definition']
            failure_path.append({
                'stage': 'definition',
                'file': definition.get('file'),
                'line': definition.get('line'),
                'symbol_type': definition.get('symbol_type')
            })
        
        # Search for error raising locations
        raise_patterns = [
            f'raise {error_id}',
            f'raise {error_id}(',
            f'except {error_id}'
        ]
        
        for pattern in raise_patterns:
            search_result = search_code(tool_context, query=pattern)
            if search_result.get('status') == 'ok':
                for match in search_result['matches']:
                    failure_path.append({
                        'stage': 'raise_or_handle',
                        'file': match['file'],
                        'line': match['line'],
                        'snippet': match['snippet']
                    })
        
        return {
            'status': 'ok',
            'error_id': error_id,
            'failure_path': failure_path,
            'note': 'Static analysis - runtime path requires execution tracing'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def set_breakpoint(
    file_path: str,
    line: int,
    tool_context: ToolContext,
    condition: Optional[str] = None
) -> dict:
    """Set a debugger breakpoint."""
    try:
        bp_id = f"bp_{file_path}:{line}"
        
        _breakpoints[bp_id] = {
            'file_path': file_path,
            'line': line,
            'condition': condition,
            'enabled': True
        }
        
        return {
            'status': 'ok',
            'file_path': file_path,
            'line': line,
            'condition': condition,
            'breakpoint_id': bp_id,
            'set': True,
            'note': 'Real breakpoint setting requires debugger integration (pdb, gdb, etc.)'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def remove_breakpoint(breakpoint_id: str, tool_context: ToolContext) -> dict:
    """Remove a breakpoint."""
    try:
        if breakpoint_id in _breakpoints:
            del _breakpoints[breakpoint_id]
            return {
                'status': 'ok',
                'breakpoint_id': breakpoint_id,
                'removed': True
            }
        
        return {
            'status': 'error',
            'error': f'Breakpoint {breakpoint_id} not found'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def step_into(tool_context: ToolContext) -> dict:
    """Step into a function."""
    try:
        # This requires active debugger session
        # For now, return status based on debugger state
        if _debugger_state['active']:
            return {
                'status': 'ok',
                'action': 'step_into',
                'executed': False,
                'note': 'Requires active debugger session with runtime integration'
            }
        else:
            return {
                'status': 'not_active',
                'action': 'step_into',
                'message': 'No active debugger session'
            }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def step_over(tool_context: ToolContext) -> dict:
    """Step over an operation."""
    try:
        if _debugger_state['active']:
            return {
                'status': 'ok',
                'action': 'step_over',
                'executed': False,
                'note': 'Requires active debugger session with runtime integration'
            }
        else:
            return {
                'status': 'not_active',
                'action': 'step_over',
                'message': 'No active debugger session'
            }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def step_out(tool_context: ToolContext) -> dict:
    """Exit the current function."""
    try:
        if _debugger_state['active']:
            return {
                'status': 'ok',
                'action': 'step_out',
                'executed': False,
                'note': 'Requires active debugger session with runtime integration'
            }
        else:
            return {
                'status': 'not_active',
                'action': 'step_out',
                'message': 'No active debugger session'
            }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def inspect_variables(
    tool_context: ToolContext,
    scope: str = 'local'
) -> dict:
    """Inspect runtime variables."""
    try:
        if _debugger_state['active']:
            return {
                'status': 'ok',
                'scope': scope,
                'variables': [],
                'note': 'Requires active debugger session with runtime integration'
            }
        else:
            return {
                'status': 'not_active',
                'scope': scope,
                'message': 'No active debugger session'
            }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def evaluate_debug_expression(
    expression: str,
    tool_context: ToolContext
) -> dict:
    """Evaluate a safe debugging expression."""
    try:
        # This requires active debugger session
        # For safety, evaluate using Python's eval with restricted globals
        allowed_globals = {'__builtins__': {}}
        try:
            result = eval(expression, allowed_globals, {})
            return {
                'status': 'ok',
                'expression': expression,
                'result': str(result),
                'type': type(result).__name__
            }
        except Exception as e:
            return {
                'status': 'error',
                'expression': expression,
                'error': str(e)
            }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def inspect_call_stack(tool_context: ToolContext) -> dict:
    """Inspect the current call stack."""
    try:
        # This requires active debugger session
        # For now, return current Python stack
        current_stack = traceback.extract_stack()
        frames = []
        
        for frame in current_stack[-10:]:  # Last 10 frames
            frames.append({
                'file': frame.filename,
                'line': frame.lineno,
                'function': frame.name
            })
        
        return {
            'status': 'ok',
            'call_stack': frames,
            'note': 'This is the current Python stack, not the debugged application stack'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def watch_expression(
    expression: str,
    tool_context: ToolContext
) -> dict:
    """Monitor an expression."""
    try:
        watch_id = f"watch_{expression}"
        
        # This would be stored in the debugger state
        return {
            'status': 'ok',
            'expression': expression,
            'watch_id': watch_id,
            'watching': True,
            'note': 'Watch expressions require active debugger integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def reproduce_bug(
    bug_report: str,
    tool_context: ToolContext
) -> dict:
    """Attempt to reproduce a failure."""
    try:
        # Parse the bug report for key information
        import re
        
        # Extract error messages
        error_patterns = re.findall(r'(?:Error|Exception):?\s*([^\n]+)', bug_report)
        
        # Extract file references
        file_patterns = re.findall(r'File\s+["\']?([^"\':\s]+)["\']?', bug_report)
        
        # Extract function references
        function_patterns = re.findall(r'(?:function|def)\s+(\w+)', bug_report)
        
        reproduction_steps = []
        
        if error_patterns:
            reproduction_steps.append({
                'step': 'search_error',
                'action': f'Search for error: {error_patterns[0]}'
            })
        
        if file_patterns:
            reproduction_steps.append({
                'step': 'check_file',
                'action': f'Inspect file: {file_patterns[0]}'
            })
        
        if function_patterns:
            reproduction_steps.append({
                'step': 'check_function',
                'action': f'Analyze function: {function_patterns[0]}'
            })
        
        return {
            'status': 'ok',
            'bug_report': bug_report,
            'extracted_info': {
                'errors': error_patterns,
                'files': file_patterns,
                'functions': function_patterns
            },
            'reproduction_steps': reproduction_steps,
            'note': 'Automated reproduction requires test execution environment'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def compare_success_failure(
    success_trace_id: str,
    failure_trace_id: str,
    tool_context: ToolContext
) -> dict:
    """Compare successful and failed executions."""
    try:
        # This would compare execution traces
        # For now, provide a framework for comparison
        return {
            'status': 'ok',
            'success_trace_id': success_trace_id,
            'failure_trace_id': failure_trace_id,
            'comparison': {
                'differences': [],
                'common_elements': [],
                'divergence_point': None
            },
            'note': 'Full comparison requires execution trace storage and analysis'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def identify_root_cause(
    error_id: str,
    tool_context: ToolContext
) -> dict:
    """Rank and explain possible root causes."""
    try:
        from .repository_tools import search_code
        from .navigation_tools import get_symbol_definition
        
        # Find the error definition
        def_result = get_symbol_definition(error_id, tool_context)
        
        possible_causes = []
        
        if def_result.get('status') == 'ok':
            # Search for where this error is raised
            raise_patterns = [f'raise {error_id}', f'raise {error_id}(']
            for pattern in raise_patterns:
                search_result = search_code(tool_context, query=pattern)
                if search_result.get('status') == 'ok':
                    for match in search_result['matches']:
                        possible_causes.append({
                            'cause': 'explicit_raise',
                            'file': match['file'],
                            'line': match['line'],
                            'snippet': match['snippet'],
                            'confidence': 0.8
                        })
        
        # Search for common error patterns
        common_causes = [
            'NoneType',
            'IndexError',
            'KeyError',
            'ValueError',
            'TypeError'
        ]
        
        for cause in common_causes:
            if cause in error_id:
                possible_causes.append({
                    'cause': f'{cause}_related',
                    'description': f'Likely related to {cause}',
                    'confidence': 0.6
                })
        
        return {
            'status': 'ok',
            'error_id': error_id,
            'possible_root_causes': possible_causes,
            'note': 'Static analysis - precise root cause requires runtime context'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def suggest_debugging_actions(
    error_id: str,
    tool_context: ToolContext
) -> dict:
    """Suggest next investigative steps."""
    try:
        # This would analyze the error and suggest actions
        # For now, return generic suggestions
        return {
            'status': 'ok',
            'error_id': error_id,
            'suggested_actions': [
                {'action': 'Analyze stack trace', 'priority': 'high'},
                {'action': 'Check error location in code', 'priority': 'high'},
                {'action': 'Review variable states', 'priority': 'medium'},
                {'action': 'Add logging for context', 'priority': 'medium'}
            ],
            'note': 'Generic suggestions - real analysis requires error context'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }
