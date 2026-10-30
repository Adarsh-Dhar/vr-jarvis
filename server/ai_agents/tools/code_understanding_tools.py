"""
Agent 4 - Code Understanding Tools
Understand what the code actually means.
"""

from typing import Optional, List, Dict, Any
import ast
from pathlib import Path
from google.adk.tools import ToolContext
from ._safe import safe
from .navigation_tools import get_symbol_definition, get_symbol_hover_info
from .analysis_tools import parse_source_code, analyze_code_complexity, analyze_control_flow


def _is_python_file(file_path: str) -> bool:
    """Check if a file is a Python file."""
    return file_path.endswith('.py')


def _parse_python_ast(file_path: str):
    """Parse Python file into AST."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return ast.parse(f.read())
    except Exception:
        return None


@safe
def parse_function(function_id: str, tool_context: ToolContext) -> dict:
    """Parse a function and its internal structure."""
    try:
        # Get function definition
        def_result = get_symbol_definition(function_id, tool_context)
        if def_result.get('status') != 'ok':
            return def_result
        
        file_path = def_result['definition']['file']
        line_num = def_result['definition']['line']
        
        if not _is_python_file(file_path):
            return {
                'status': 'not_applicable',
                'function_id': function_id,
                'message': 'Function parsing only implemented for Python'
            }
        
        tree = _parse_python_ast(file_path)
        if not tree:
            return {
                'status': 'error',
                'error': 'Could not parse file'
            }
        
        # Find the function in AST
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == function_id:
                parameters = [arg.arg for arg in node.args.args]
                statements = []
                
                for stmt in node.body:
                    stmt_type = type(stmt).__name__
                    statements.append({
                        'type': stmt_type,
                        'line': stmt.lineno
                    })
                
                return {
                    'status': 'ok',
                    'function_id': function_id,
                    'structure': {
                        'parameters': parameters,
                        'statements': statements,
                        'decorators': [ast.unparse(d) for d in node.decorator_list] if hasattr(ast, 'unparse') else []
                    }
                }
        
        return {
            'status': 'not_found',
            'function_id': function_id,
            'message': 'Function not found in AST'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def explain_function(
    function_id: str,
    tool_context: ToolContext,
    level: str = 'intermediate'
) -> dict:
    """Explain the function's purpose and behavior."""
    try:
        # Get hover info for documentation
        hover_result = get_symbol_hover_info(function_id, tool_context)
        
        # Get complexity info
        def_result = get_symbol_definition(function_id, tool_context)
        complexity_info = {}
        if def_result.get('status') == 'ok':
            file_path = def_result['definition']['file']
            complexity_result = analyze_code_complexity(file_path, tool_context)
            if complexity_result.get('status') == 'ok':
                complexity_info = complexity_result.get('complexity', {})
        
        # Build explanation based on level
        if hover_result.get('status') == 'ok':
            docstring = hover_result.get('documentation', '')
            signature = hover_result.get('signature', '')
            
            if level == 'beginner':
                explanation = f"Function {function_id} is defined as: {signature}"
                if docstring:
                    explanation += f". {docstring}"
            elif level == 'advanced':
                explanation = f"{signature}"
                if docstring:
                    explanation += f"\n\nDocumentation: {docstring}"
                if complexity_info:
                    explanation += f"\n\nComplexity: {complexity_info}"
            else:  # intermediate
                explanation = f"{function_id}: {signature}"
                if docstring:
                    explanation += f" - {docstring}"
        else:
            explanation = f"Function {function_id} could not be analyzed."
        
        return {
            'status': 'ok',
            'function_id': function_id,
            'explanation': explanation,
            'level': level,
            'complexity': complexity_info
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def explain_class(class_id: str, tool_context: ToolContext) -> dict:
    """Explain a class and its responsibilities."""
    try:
        def_result = get_symbol_definition(class_id, tool_context)
        if def_result.get('status') != 'ok':
            return def_result
        
        file_path = def_result['definition']['file']
        
        if not _is_python_file(file_path):
            return {
                'status': 'not_applicable',
                'class_id': class_id,
                'message': 'Class analysis only implemented for Python'
            }
        
        tree = _parse_python_ast(file_path)
        if not tree:
            return {
                'status': 'error',
                'error': 'Could not parse file'
            }
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_id:
                methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                base_classes = [ast.unparse(base) for base in node.bases] if hasattr(ast, 'unparse') else []
                
                # Infer responsibilities from method names
                responsibilities = []
                for method in methods:
                    if 'get' in method.lower():
                        responsibilities.append(f'retrieve {method.replace("get_", "")}')
                    elif 'set' in method.lower():
                        responsibilities.append(f'modify {method.replace("set_", "")}')
                    elif 'validate' in method.lower():
                        responsibilities.append('validation')
                    elif 'process' in method.lower():
                        responsibilities.append('processing')
                
                return {
                    'status': 'ok',
                    'class_id': class_id,
                    'explanation': f"Class {class_id} provides {len(methods)} methods for {', '.join(responsibilities[:3])}.",
                    'responsibilities': responsibilities,
                    'methods': methods,
                    'base_classes': base_classes
                }
        
        return {
            'status': 'not_found',
            'class_id': class_id,
            'message': 'Class not found in AST'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def explain_module(module_path: str, tool_context: ToolContext) -> dict:
    """Explain a module."""
    try:
        from .navigation_tools import get_exports
        from .repository_tools import list_files
        
        path = Path(module_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'Module not found: {module_path}'
            }
        
        # Get exports
        exports_result = get_exports(str(path), tool_context)
        exports = exports_result.get('exports', []) if exports_result.get('status') == 'ok' else []
        
        # List files in module
        files_result = list_files(tool_context, directory=str(path), recursive=False)
        files = files_result.get('files', []) if files_result.get('status') == 'ok' else []
        
        # Infer purpose from exports
        purpose = 'general utilities'
        if any('test' in e['name'].lower() for e in exports):
            purpose = 'testing utilities'
        elif any('auth' in e['name'].lower() for e in exports):
            purpose = 'authentication'
        elif any('db' in e['name'].lower() or 'database' in e['name'].lower() for e in exports):
            purpose = 'database operations'
        
        return {
            'status': 'ok',
            'module_path': module_path,
            'explanation': f"This module provides {purpose} with {len(exports)} exported symbols.",
            'exports': [e['name'] for e in exports],
            'files': [f['path'] for f in files if f['type'] == 'file']
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def explain_variable(variable_id: str, tool_context: ToolContext) -> dict:
    """Explain a variable's purpose and usage."""
    try:
        from .navigation_tools import get_scope_information
        from .repository_tools import search_code
        
        # Search for variable usage
        search_result = search_code(tool_context, query=variable_id)
        
        if search_result.get('status') != 'ok' or not search_result.get('matches'):
            return {
                'status': 'not_found',
                'variable_id': variable_id,
                'message': 'Variable usage not found'
            }
        
        # Analyze usage patterns
        matches = search_result['matches']
        usage_count = len(matches)
        
        # Infer type from common patterns
        var_type = 'unknown'
        if any('=' in m.get('snippet', '') and '"' in m.get('snippet', '') for m in matches):
            var_type = 'str'
        elif any('=' in m.get('snippet', '') and str(m.get('snippet', '')).isdigit() for m in matches):
            var_type = 'int'
        elif any('=' in m.get('snippet', '') and 'True' in m.get('snippet', '') for m in matches):
            var_type = 'bool'
        
        return {
            'status': 'ok',
            'variable_id': variable_id,
            'explanation': f"Variable {variable_id} is used {usage_count} times across the codebase.",
            'type': var_type,
            'usage_count': usage_count,
            'locations': [m['file'] for m in matches[:5]]
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def explain_expression(
    expression: str,
    file_path: str,
    line: int,
    tool_context: ToolContext
) -> dict:
    """Explain an individual expression."""
    try:
        if not _is_python_file(file_path):
            return {
                'status': 'not_applicable',
                'message': 'Expression analysis only implemented for Python'
            }
        
        tree = _parse_python_ast(file_path)
        if not tree:
            return {
                'status': 'error',
                'error': 'Could not parse file'
            }
        
        # Find the line and analyze expression
        for node in ast.walk(tree):
            if hasattr(node, 'lineno') and node.lineno == line:
                expr_type = type(node).__name__
                
                # Determine explanation based on type
                explanations = {
                    'BinOp': 'This is a binary operation combining two values.',
                    'Compare': 'This is a comparison between values.',
                    'Call': 'This is a function call.',
                    'Attribute': 'This accesses an attribute of an object.',
                    'Subscript': 'This accesses an element of a collection.',
                    'List': 'This is a list literal.',
                    'Dict': 'This is a dictionary literal.',
                    'Lambda': 'This is an anonymous function.',
                    'UnaryOp': 'This is a unary operation on a single value.'
                }
                
                explanation = explanations.get(expr_type, f'This is a {expr_type} expression.')
                
                return {
                    'status': 'ok',
                    'expression': expression,
                    'explanation': explanation,
                    'type': expr_type
                }
        
        return {
            'status': 'not_found',
            'message': f'Could not find expression at line {line}'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def explain_condition(
    condition_id: str,
    tool_context: ToolContext
) -> dict:
    """Explain conditional logic."""
    try:
        from .repository_tools import search_code
        
        # Search for the condition
        search_result = search_code(tool_context, query=condition_id)
        
        if search_result.get('status') != 'ok':
            return search_result
        
        matches = search_result.get('matches', [])
        
        if not matches:
            return {
                'status': 'not_found',
                'condition_id': condition_id,
                'message': 'Condition not found'
            }
        
        # Analyze the first match
        match = matches[0]
        snippet = match.get('snippet', '')
        
        # Determine condition type
        condition_type = 'unknown'
        if 'if' in snippet.lower():
            condition_type = 'conditional'
        elif 'while' in snippet.lower():
            condition_type = 'loop'
        elif 'and' in snippet.lower() or 'or' in snippet.lower():
            condition_type = 'compound'
        
        return {
            'status': 'ok',
            'condition_id': condition_id,
            'explanation': f"This {condition_type} checks: {snippet.strip()}",
            'type': condition_type,
            'snippet': snippet
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def explain_algorithm(
    function_id: str,
    tool_context: ToolContext
) -> dict:
    """Explain the algorithm being used."""
    try:
        # Get control flow analysis
        cf_result = analyze_control_flow(function_id, tool_context)
        
        if cf_result.get('status') != 'ok':
            return cf_result
        
        control_flow = cf_result.get('control_flow', {})
        branches = control_flow.get('branches', [])
        loops = control_flow.get('loops', [])
        
        # Infer algorithm from patterns
        algorithm = 'sequential'
        complexity = 'O(n)'
        explanation = 'This function processes data sequentially.'
        
        if loops:
            if any(l['type'] == 'for' for l in loops):
                algorithm = 'iteration'
                complexity = 'O(n)'
                explanation = 'This function iterates over a collection.'
            if any(l['type'] == 'while' for l in loops):
                algorithm = 'conditional_loop'
                complexity = 'O(n)'
                explanation = 'This function uses a while loop for processing.'
        
        if len(loops) > 1:
            algorithm = 'nested_loop'
            complexity = 'O(n^2)'
            explanation = 'This function uses nested loops, which may have quadratic complexity.'
        
        if branches and not loops:
            algorithm = 'branching'
            complexity = 'O(1)'
            explanation = 'This function uses conditional branching without iteration.'
        
        return {
            'status': 'ok',
            'function_id': function_id,
            'algorithm': algorithm,
            'complexity': complexity,
            'explanation': explanation,
            'branches': len(branches),
            'loops': len(loops)
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def extract_function_signature(function_id: str, tool_context: ToolContext) -> dict:
    """Extract parameters and return types."""
    try:
        hover_result = get_symbol_hover_info(function_id, tool_context)
        
        if hover_result.get('status') != 'ok':
            return hover_result
        
        signature = hover_result.get('signature', '')
        
        # Parse signature to extract components
        # Simple regex-based parsing
        import re
        
        # Match function name and parameters
        match = re.match(r'def\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*([^:]+))?', signature)
        
        if match:
            name = match.group(1)
            params_str = match.group(2)
            return_type = match.group(3) or 'None'
            
            parameters = []
            if params_str.strip():
                for param in params_str.split(','):
                    param = param.strip()
                    if ':' in param:
                        param_name, param_type = param.split(':', 1)
                        parameters.append({
                            'name': param_name.strip(),
                            'type': param_type.strip()
                        })
                    else:
                        parameters.append({
                            'name': param,
                            'type': 'Any'
                        })
            
            return {
                'status': 'ok',
                'function_id': function_id,
                'signature': {
                    'name': name,
                    'parameters': parameters,
                    'return_type': return_type.strip()
                }
            }
        
        return {
            'status': 'ok',
            'function_id': function_id,
            'signature': {
                'name': function_id,
                'parameters': [],
                'return_type': 'unknown',
                'raw': signature
            }
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def extract_function_contract(function_id: str, tool_context: ToolContext) -> dict:
    """Identify preconditions, postconditions and invariants."""
    try:
        # This is a simplified implementation
        # Real contract extraction would require more sophisticated analysis
        
        parse_result = parse_function(function_id, tool_context)
        if parse_result.get('status') != 'ok':
            return parse_result
        
        # Infer conditions from parameter names and function name
        function_name_lower = function_id.lower()
        parameters = parse_result['structure'].get('parameters', [])
        
        preconditions = []
        postconditions = []
        
        # Infer from function name
        if 'validate' in function_name_lower or 'check' in function_name_lower:
            postconditions.append('returns boolean indicating validity')
        if 'process' in function_name_lower or 'transform' in function_name_lower:
            preconditions.append('input is not None')
            postconditions.append('returns processed result')
        
        # Infer from parameter names
        for param in parameters:
            if 'count' in param.lower() or 'num' in param.lower():
                preconditions.append(f'{param} >= 0')
            if 'id' in param.lower():
                preconditions.append(f'{param} is valid identifier')
        
        return {
            'status': 'ok',
            'function_id': function_id,
            'contract': {
                'preconditions': preconditions,
                'postconditions': postconditions,
                'invariants': [],
                'note': 'Contract inference is heuristic-based'
            }
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def identify_side_effects(function_id: str, tool_context: ToolContext) -> dict:
    """Identify external effects of code execution."""
    try:
        from .repository_tools import search_code
        
        # Search for function definition to analyze body
        def_result = get_symbol_definition(function_id, tool_context)
        if def_result.get('status') != 'ok':
            return def_result
        
        file_path = def_result['definition']['file']
        
        if not _is_python_file(file_path):
            return {
                'status': 'not_applicable',
                'function_id': function_id,
                'message': 'Side effect analysis only implemented for Python'
            }
        
        tree = _parse_python_ast(file_path)
        if not tree:
            return {
                'status': 'error',
                'error': 'Could not parse file'
            }
        
        side_effects = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == function_id:
                for child in ast.walk(node):
                    # Check for common side effect patterns
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Attribute):
                            attr = child.func.attr.lower()
                            if attr in ['write', 'save', 'append', 'extend', 'insert', 'delete', 'remove']:
                                side_effects.append({
                                    'type': 'mutation',
                                    'target': attr
                                })
                            elif attr in ['open', 'close', 'connect', 'disconnect']:
                                side_effects.append({
                                    'type': 'resource_operation',
                                    'target': attr
                                })
                        elif isinstance(child.func, ast.Name):
                            name = child.func.id.lower()
                            if name in ['print', 'log', 'debug', 'info', 'warn']:
                                side_effects.append({
                                    'type': 'io_operation',
                                    'target': name
                                })
                            elif name in ['execute', 'run', 'call']:
                                side_effects.append({
                                    'type': 'external_call',
                                    'target': name
                                })
                break
        
        return {
            'status': 'ok',
            'function_id': function_id,
            'side_effects': side_effects,
            'has_side_effects': len(side_effects) > 0
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def identify_hidden_assumptions(function_id: str, tool_context: ToolContext) -> dict:
    """Find assumptions embedded in implementation."""
    try:
        # This is a heuristic-based implementation
        # Real assumption detection would require more sophisticated analysis
        
        def_result = get_symbol_definition(function_id, tool_context)
        if def_result.get('status') != 'ok':
            return def_result
        
        file_path = def_result['definition']['file']
        
        if not _is_python_file(file_path):
            return {
                'status': 'not_applicable',
                'function_id': function_id,
                'message': 'Assumption analysis only implemented for Python'
            }
        
        tree = _parse_python_ast(file_path)
        if not tree:
            return {
                'status': 'error',
                'error': 'Could not parse file'
            }
        
        assumptions = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == function_id:
                # Check for direct attribute access without checks
                for child in ast.walk(node):
                    if isinstance(child, ast.Attribute):
                        assumptions.append({
                            'assumption': f'object has attribute {child.attr}',
                            'confidence': 0.6
                        })
                    # Check for list/dict indexing without bounds check
                    elif isinstance(child, ast.Subscript):
                        assumptions.append({
                            'assumption': 'index is within bounds',
                            'confidence': 0.7
                        })
                break
        
        return {
            'status': 'ok',
            'function_id': function_id,
            'assumptions': assumptions,
            'assumption_count': len(assumptions)
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def infer_code_intent(function_id: str, tool_context: ToolContext) -> dict:
    """Infer intended behavior from evidence."""
    try:
        # Get function info
        def_result = get_symbol_definition(function_id, tool_context)
        hover_result = get_symbol_hover_info(function_id, tool_context)
        
        if def_result.get('status') != 'ok':
            return def_result
        
        function_name = function_id.lower()
        evidence = []
        intent = 'general operation'
        confidence = 0.5
        
        # Infer intent from function name
        if 'validate' in function_name or 'check' in function_name:
            intent = 'validation'
            confidence = 0.9
            evidence.append('function name suggests validation')
        elif 'process' in function_name or 'transform' in function_name:
            intent = 'data processing'
            confidence = 0.85
            evidence.append('function name suggests processing')
        elif 'get' in function_name or 'fetch' in function_name or 'retrieve' in function_name:
            intent = 'data retrieval'
            confidence = 0.9
            evidence.append('function name suggests retrieval')
        elif 'set' in function_name or 'update' in function_name or 'modify' in function_name:
            intent = 'modification'
            confidence = 0.85
            evidence.append('function name suggests modification')
        elif 'calculate' in function_name or 'compute' in function_name:
            intent = 'computation'
            confidence = 0.9
            evidence.append('function name suggests calculation')
        elif 'parse' in function_name:
            intent = 'parsing'
            confidence = 0.9
            evidence.append('function name suggests parsing')
        
        # Add evidence from docstring
        if hover_result.get('status') == 'ok':
            docstring = hover_result.get('documentation', '')
            if docstring:
                evidence.append('has documentation')
                confidence = min(0.95, confidence + 0.05)
        
        return {
            'status': 'ok',
            'function_id': function_id,
            'intent': intent,
            'confidence': confidence,
            'evidence': evidence
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def compare_implementations(
    function1_id: str,
    function2_id: str,
    tool_context: ToolContext
) -> dict:
    """Compare multiple implementations."""
    try:
        # Get complexity for both functions
        def1 = get_symbol_definition(function1_id, tool_context)
        def2 = get_symbol_definition(function2_id, tool_context)
        
        if def1.get('status') != 'ok' or def2.get('status') != 'ok':
            return {
                'status': 'error',
                'error': 'Could not find one or both functions'
            }
        
        file1 = def1['definition']['file']
        file2 = def2['definition']['file']
        
        comp1 = analyze_code_complexity(file1, tool_context)
        comp2 = analyze_code_complexity(file2, tool_context)
        
        complexity1 = comp1.get('complexity', {}).get('cyclomatic', 0) if comp1.get('status') == 'ok' else 0
        complexity2 = comp2.get('complexity', {}).get('cyclomatic', 0) if comp2.get('status') == 'ok' else 0
        
        # Get algorithm info
        algo1 = explain_algorithm(function1_id, tool_context)
        algo2 = explain_algorithm(function2_id, tool_context)
        
        comparison = {
            'complexity': {
                'function1': complexity1,
                'function2': complexity2,
                'simpler': function1_id if complexity1 < complexity2 else function2_id
            },
            'algorithm': {
                'function1': algo1.get('algorithm', 'unknown'),
                'function2': algo2.get('algorithm', 'unknown')
            }
        }
        
        return {
            'status': 'ok',
            'function1': function1_id,
            'function2': function2_id,
            'comparison': comparison
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_function_logic(function_id: str, tool_context: ToolContext) -> dict:
    """Explain the function's logic step by step."""
    try:
        parse_result = parse_function(function_id, tool_context)
        if parse_result.get('status') != 'ok':
            return parse_result
        
        statements = parse_result['structure'].get('statements', [])
        
        steps = []
        for i, stmt in enumerate(statements, 1):
            step_desc = f"Execute {stmt['type']}"
            if stmt['type'] == 'If':
                step_desc = "Evaluate condition"
            elif stmt['type'] == 'Return':
                step_desc = "Return result"
            elif stmt['type'] == 'Assign':
                step_desc = "Assign value"
            
            steps.append({
                'step': i,
                'line': stmt['line'],
                'action': step_desc,
                'type': stmt['type']
            })
        
        return {
            'status': 'ok',
            'function_id': function_id,
            'steps': steps,
            'total_steps': len(steps)
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def generate_code_summary(
    element_id: str,
    tool_context: ToolContext
) -> dict:
    """Create a concise semantic summary."""
    try:
        # Try to determine if it's a function or class
        def_result = get_symbol_definition(element_id, tool_context)
        
        if def_result.get('status') == 'ok':
            symbol_type = def_result['definition'].get('symbol_type', 'unknown')
            
            if symbol_type == 'function':
                # Get function explanation
                explain_result = explain_function(element_id, tool_context, level='intermediate')
                if explain_result.get('status') == 'ok':
                    return {
                        'status': 'ok',
                        'element_id': element_id,
                        'type': 'function',
                        'summary': explain_result.get('explanation', ''),
                        'key_points': []
                    }
            elif symbol_type == 'class':
                # Get class explanation
                class_result = explain_class(element_id, tool_context)
                if class_result.get('status') == 'ok':
                    return {
                        'status': 'ok',
                        'element_id': element_id,
                        'type': 'class',
                        'summary': class_result.get('explanation', ''),
                        'key_points': class_result.get('responsibilities', [])
                    }
        
        # Fallback to general summary
        return {
            'status': 'ok',
            'element_id': element_id,
            'summary': f"Code element {element_id} defined in the codebase.",
            'key_points': []
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }
