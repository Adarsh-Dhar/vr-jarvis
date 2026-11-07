"""
Agent 6 - Data Flow Intelligence Tools
Understand how data moves through the entire application.
"""

from typing import Optional, List, Dict, Any
from google.adk.tools import ToolContext
from ._safe import safe
import ast


def _is_python_file(file_path: str) -> bool:
    return file_path.endswith('.py')


def _parse_python_ast(file_path: str) -> Optional[ast.AST]:
    try:
        from pathlib import Path
        content = Path(file_path).read_text(encoding='utf-8')
        return ast.parse(content)
    except Exception:
        return None


class DefUseAnalyzer(ast.NodeVisitor):
    """AST visitor to collect definition-use chains within a function."""
    
    def __init__(self):
        self.definitions = {}  # variable -> {line, type}
        self.uses = []  # list of {variable, line, type}
        self.def_use_edges = []  # list of {from_var, to_var, line, kind}
    
    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.definitions[target.id] = {'line': node.lineno, 'type': 'assignment'}
                # Check if RHS is a variable (creating a data flow edge)
                if isinstance(node.value, ast.Name):
                    self.def_use_edges.append({
                        'from': node.value.id,
                        'to': target.id,
                        'line': node.lineno,
                        'kind': 'assignment'
                    })
        self.generic_visit(node)
    
    def visit_AugAssign(self, node):
        if isinstance(node.target, ast.Name):
            self.definitions[node.target.id] = {'line': node.lineno, 'type': 'augmented_assignment'}
            if isinstance(node.value, ast.Name):
                self.def_use_edges.append({
                    'from': node.value.id,
                    'to': node.target.id,
                    'line': node.lineno,
                    'kind': 'augmented'
                })
        self.generic_visit(node)
    
    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.uses.append({'variable': node.id, 'line': node.lineno, 'type': 'load'})
        self.generic_visit(node)
    
    def visit_Call(self, node):
        # Track arguments passed to function calls
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            for i, arg in enumerate(node.args):
                if isinstance(arg, ast.Name):
                    self.def_use_edges.append({
                        'from': arg.id,
                        'to': f'{func_name}_param_{i}',
                        'line': node.lineno,
                        'kind': 'call_argument'
                    })
        self.generic_visit(node)
    
    def visit_Return(self, node):
        if node.value and isinstance(node.value, ast.Name):
            self.def_use_edges.append({
                'from': node.value.id,
                'to': 'return_value',
                'line': node.lineno,
                'kind': 'return'
            })
        self.generic_visit(node)


@safe
def trace_variable_origin(variable_id: str, tool_context: ToolContext) -> dict:
    """Find where a variable's value originates using def-use analysis."""
    try:
        from ..intelligence.graph_engine.codegraph import codegraph
        
        # Parse variable_id as function:variable
        if ':' not in variable_id:
            return {
                'status': 'error',
                'error': 'Variable ID must be in format function:variable'
            }
        
        function_name, variable_name = variable_id.split('#', 1)
        
        # Use CodeGraph to resolve the function
        graph = codegraph.load_current_graph()
        node = graph.get(function_name)
        
        if not node:
            return {
                'status': 'not_found',
                'function_name': function_name,
                'message': 'Function not found in graph'
            }
        
        file_path = node.get('file', '')
        
        if not _is_python_file(file_path):
            return {
                'status': 'not_applicable',
                'message': 'Data flow analysis only implemented for Python'
            }
        
        tree = _parse_python_ast(file_path)
        if not tree:
            return {
                'status': 'error',
                'error': 'Could not parse file'
            }
        
        # Find the function node
        func_node = None
        simple_name = node.get('name', '')
        if not simple_name and '.' in node.get('id', ''):
            simple_name = node['id'].split('.')[-1]
        
        for node_ast in ast.walk(tree):
            if isinstance(node_ast, ast.FunctionDef) and node_ast.name == simple_name:
                func_node = node_ast
                break
        
        if not func_node:
            return {
                'status': 'not_found',
                'message': f'Function {function_name} not found'
            }
        
        # Run def-use analysis
        analyzer = DefUseAnalyzer()
        analyzer.visit(func_node)
        
        # Find where variable is defined
        if variable_name in analyzer.definitions:
            origin = analyzer.definitions[variable_name]
            return {
                'status': 'ok',
                'variable_id': variable_id,
                'origin': {
                    'file': file_path,
                    'line': origin['line'],
                    'type': origin['type']
                }
            }
        
        # Check if it's a parameter
        for arg in func_node.args.args:
            if arg.arg == variable_name:
                return {
                    'status': 'ok',
                    'variable_id': variable_id,
                    'origin': {
                        'file': file_path,
                        'line': func_node.lineno,
                        'type': 'parameter'
                    }
                }
        
        return {
            'status': 'not_found',
            'variable_id': variable_id,
            'message': f'Variable {variable_name} not found in function {function_name}'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_variable_usage(variable_id: str, tool_context: ToolContext) -> dict:
    """Find where a variable is used using def-use analysis."""
    try:
        from ..intelligence.graph_engine.codegraph import codegraph
        
        if ':' not in variable_id:
            return {
                'status': 'error',
                'error': 'Variable ID must be in format function:variable'
            }
        
        function_name, variable_name = variable_id.split('#', 1)
        
        # Use CodeGraph to resolve the function
        graph = codegraph.load_current_graph()
        node = graph.get(function_name)
        
        if not node:
            return {
                'status': 'not_found',
                'function_name': function_name,
                'message': 'Function not found in graph'
            }
        
        file_path = node.get('file', '')
        
        if not _is_python_file(file_path):
            return {
                'status': 'not_applicable',
                'message': 'Data flow analysis only implemented for Python'
            }
        
        tree = _parse_python_ast(file_path)
        if not tree:
            return {
                'status': 'error',
                'error': 'Could not parse file'
            }
        
        func_node = None
        simple_name = node.get('name', '')
        if not simple_name and '.' in node.get('id', ''):
            simple_name = node['id'].split('.')[-1]
        
        for node_ast in ast.walk(tree):
            if isinstance(node_ast, ast.FunctionDef) and node_ast.name == simple_name:
                func_node = node_ast
                break
        
        if not func_node:
            return {
                'status': 'not_found',
                'message': f'Function {function_name} not found'
            }
        
        analyzer = DefUseAnalyzer()
        analyzer.visit(func_node)
        
        # Find all uses of the variable
        uses = [u for u in analyzer.uses if u['variable'] == variable_name]
        
        return {
            'status': 'ok',
            'variable_id': variable_id,
            'uses': uses,
            'use_count': len(uses)
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Helper to normalize AST names
def get_ast_name(node):
    """Get the normalized name of an AST node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = get_ast_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def get_call_name(node):
    """Get the normalized call name from an AST Call node."""
    if isinstance(node, ast.Call):
        return get_ast_name(node.func)
    return ""


# Taint sources - exact normalized names
SOURCE_CALLS = {
    'input',
    'builtins.input',
    'os.getenv',
    'os.environ.get',
    'request.args.get',
    'request.form.get',
    'request.query_params.get',
    'request.get_json',
    'request.json',
    'request.data',
    'sys.argv',
}

# Taint sources that use subscript notation
SOURCE_SUBSCRIPTS = {
    'request.args',
    'request.form',
    'request.query_params',
}

# Taint sinks - exact normalized names
SINK_CALLS = {
    'eval',
    'exec',
    'compile',
    'cursor.execute',
    'cursor.executemany',
    'connection.execute',
    'os.system',
    'os.popen',
    'subprocess.run',
    'subprocess.call',
    'subprocess.Popen',
}


def analyze_python_taint_source(source_code: str, file_path: str) -> dict:
    """Analyze Python source code for taint flows with provenance tracking.

    This is a testable, pure Python helper that analyzes source code directly
    without requiring graph resolution. Returns sources, sinks, and paths with
    complete provenance chains.

    Args:
        source_code: The Python source code to analyze
        file_path: The file path for context (used in results)

    Returns:
        dict with 'sources', 'sinks', 'paths', 'safe_cases', 'status'
    """
    try:
        tree = ast.parse(source_code)

        # Provenance tracking structures
        # tainted_variables: var_name -> {source_id: full_step_chain}
        # Each step chain is a complete provenance snapshot from source to this variable
        tainted_variables = {}
        provenance_registry = {}  # source_id -> {source_metadata} (immutable)
        source_counter = 0
        captured_paths = []  # Capture paths at sink visit time

        def _create_source_id():
            nonlocal source_counter
            source_counter += 1
            return f"source_{source_counter:03d}"

        def _is_taint_source(node):
            """Check if node is a taint source using exact AST matching."""
            if isinstance(node, ast.Call):
                call_name = get_call_name(node)
                return call_name in SOURCE_CALLS
            if isinstance(node, ast.Attribute):
                # Handle attribute sources like request.json
                attr_name = get_ast_name(node)
                return attr_name in SOURCE_CALLS
            if isinstance(node, ast.Subscript):
                # Handle subscript sources like sys.argv[1] or request.args["id"]
                base_name = get_ast_name(node.value)
                if base_name in SOURCE_CALLS:
                    return True
                # Handle dictionary subscript forms like request.args["id"]
                if base_name in SOURCE_SUBSCRIPTS:
                    return True
            return False

        def _evaluate_tainted_expression(node):
            """Evaluate an AST expression and return dict of source_id -> step_chain."""
            result = {}

            if isinstance(node, ast.Name):
                # Simple variable lookup - copy the variable's step chains
                if node.id in tainted_variables:
                    for sid, steps in tainted_variables[node.id].items():
                        result[sid] = steps.copy()

            elif isinstance(node, ast.Call):
                # Check if this is a source
                if _is_taint_source(node):
                    # This is a new source
                    source_id = _create_source_id()
                    call_name = get_call_name(node)
                    provenance_registry[source_id] = {
                        'source': {
                            'call': call_name,
                            'file': file_path,
                            'line': node.lineno
                        }
                    }
                    result[source_id] = [{
                        'kind': 'source',
                        'call': call_name,
                        'line': node.lineno
                    }]

                else:
                    # Propagate through method calls (e.g., var.strip())
                    if isinstance(node.func, ast.Attribute):
                        # Check if the receiver is tainted
                        receiver_chains = _evaluate_tainted_expression(node.func.value)
                        if receiver_chains:
                            call_name = get_call_name(node)
                            for sid, steps in receiver_chains.items():
                                # Add transformation step
                                result[sid] = steps + [{
                                    'kind': 'transform',
                                    'call': call_name,
                                    'line': node.lineno
                                }]

                    # Check arguments and combine
                    for arg in node.args:
                        arg_chains = _evaluate_tainted_expression(arg)
                        for sid, steps in arg_chains.items():
                            if sid in result:
                                # Already have this source from receiver or another arg
                                continue
                            result[sid] = steps.copy()

            elif isinstance(node, ast.Attribute):
                # Check if this is a direct source (e.g., request.json)
                if _is_taint_source(node):
                    source_id = _create_source_id()
                    attr_name = get_ast_name(node)
                    provenance_registry[source_id] = {
                        'source': {
                            'call': attr_name,
                            'file': file_path,
                            'line': node.lineno
                        }
                    }
                    result[source_id] = [{
                        'kind': 'source',
                        'call': attr_name,
                        'line': node.lineno
                    }]
                else:
                    # Propagate from receiver
                    result = _evaluate_tainted_expression(node.value)

            elif isinstance(node, ast.Subscript):
                # Check if this is a source (e.g., sys.argv[1] or request.args["id"])
                if _is_taint_source(node):
                    source_id = _create_source_id()
                    base_name = get_ast_name(node.value)
                    # Include the subscript in the call name for dictionary forms
                    call_name = base_name
                    if base_name in SOURCE_SUBSCRIPTS:
                        call_name = f"{base_name}[...]"
                    provenance_registry[source_id] = {
                        'source': {
                            'call': call_name,
                            'file': file_path,
                            'line': node.lineno
                        }
                    }
                    result[source_id] = [{
                        'kind': 'source',
                        'call': call_name,
                        'line': node.lineno
                    }]
                else:
                    # Propagate from the subscripted value
                    result = _evaluate_tainted_expression(node.value)

            elif isinstance(node, ast.BinOp):
                # Combine operands (concatenation, % formatting, etc.)
                left_chains = _evaluate_tainted_expression(node.left)
                right_chains = _evaluate_tainted_expression(node.right)
                for sid, steps in left_chains.items():
                    result[sid] = steps.copy()
                for sid, steps in right_chains.items():
                    result[sid] = steps.copy()

            elif isinstance(node, ast.JoinedStr):
                # F-string: propagate through formatted values
                for value in node.values:
                    if isinstance(value, ast.FormattedValue):
                        value_chains = _evaluate_tainted_expression(value.value)
                        for sid, steps in value_chains.items():
                            result[sid] = steps.copy()

            elif isinstance(node, ast.IfExp):
                # Conditional expression: conservative combination
                body_chains = _evaluate_tainted_expression(node.body)
                orelse_chains = _evaluate_tainted_expression(node.orelse)
                for sid, steps in body_chains.items():
                    result[sid] = steps.copy()
                for sid, steps in orelse_chains.items():
                    result[sid] = steps.copy()

            return result

        class TaintVisitor(ast.NodeVisitor):
            def __init__(self):
                self.sources = []
                self.sinks = []
                self.safe_cases = []

            def visit_FunctionDef(self, node):
                # Reset environment for each function (function-scoped)
                old_tainted = tainted_variables.copy()
                tainted_variables.clear()
                self.generic_visit(node)
                tainted_variables.clear()
                # Restore outer scope (though we don't track interprocedural yet)
                for k, v in old_tainted.items():
                    tainted_variables[k] = v

            def visit_Assign(self, node):
                # Evaluate RHS once to get step chains
                rhs_chains = _evaluate_tainted_expression(node.value)

                # Assign to each target
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        var_name = target.id

                        if rhs_chains:
                            # Create new step chains for this variable
                            var_flow = {}
                            for sid, steps in rhs_chains.items():
                                # Copy the chain and add assignment step
                                var_flow[sid] = steps + [{
                                    'kind': 'assignment',
                                    'variable': var_name,
                                    'line': node.lineno
                                }]
                            tainted_variables[var_name] = var_flow
                        else:
                            # Clean assignment - remove taint
                            if var_name in tainted_variables:
                                del tainted_variables[var_name]

                self.generic_visit(node)

            def visit_AugAssign(self, node):
                # Augmented assignment: combine existing with RHS
                if isinstance(node.target, ast.Name):
                    var_name = node.target.id

                    rhs_chains = _evaluate_tainted_expression(node.value)
                    existing_flow = tainted_variables.get(var_name, {})

                    # Combine sources
                    combined_chains = {}
                    for sid, steps in existing_flow.items():
                        combined_chains[sid] = steps + [{
                            'kind': 'augmented_assignment',
                            'variable': var_name,
                            'line': node.lineno
                        }]
                    for sid, steps in rhs_chains.items():
                        if sid not in combined_chains:
                            combined_chains[sid] = steps + [{
                                'kind': 'augmented_assignment',
                                'variable': var_name,
                                'line': node.lineno
                            }]

                    if combined_chains:
                        tainted_variables[var_name] = combined_chains
                    else:
                        if var_name in tainted_variables:
                            del tainted_variables[var_name]

                self.generic_visit(node)

            def visit_Call(self, node):
                # Check for sinks
                call_name = get_call_name(node)
                is_sink = call_name in SINK_CALLS

                if is_sink:
                    # Check for safe cases (e.g., parameterized SQL)
                    is_safe = False
                    if 'execute' in call_name and len(node.args) > 1:
                        # Check if the first argument is a literal string with placeholders
                        if isinstance(node.args[0], ast.Constant):
                            sql_str = node.args[0].value
                            if isinstance(sql_str, str):
                                # Check for common placeholder patterns
                                if any(marker in sql_str for marker in ['%s', '?', ':param', '@param', '$1']):
                                    is_safe = True
                                    self.safe_cases.append({
                                        'line': node.lineno,
                                        'call': call_name,
                                        'reason': 'parameterized_query'
                                    })

                    if not is_safe:
                        # Evaluate sink arguments to get step chains
                        for arg in node.args:
                            arg_chains = _evaluate_tainted_expression(arg)
                            for source_id, steps in arg_chains.items():
                                # Capture the complete path at sink visit time
                                path_counter = len(captured_paths) + 1
                                source_meta = provenance_registry.get(source_id, {}).get('source', {})
                                captured_paths.append({
                                    'id': f'taint_path_{path_counter:03d}',
                                    'kind': 'heuristic',
                                    'source': source_meta,
                                    'sink': {
                                        'call': call_name,
                                        'file': file_path,
                                        'line': node.lineno
                                    },
                                    'steps': steps + [{
                                        'kind': 'sink',
                                        'call': call_name,
                                        'line': node.lineno
                                    }]
                                })
                                self.sinks.append({
                                    'line': node.lineno,
                                    'call': call_name,
                                    'kind': 'sink',
                                    'source_ids': [source_id]
                                })

                self.generic_visit(node)

        visitor = TaintVisitor()
        visitor.visit(tree)

        # Also collect source metadata for compatibility
        sources_list = []
        for source_id, meta in provenance_registry.items():
            sources_list.append({
                'source_id': source_id,
                **meta['source']
            })

        return {
            'status': 'ok',
            'sources': sources_list,
            'sinks': visitor.sinks,
            'paths': captured_paths,
            'safe_cases': visitor.safe_cases,
            'path_count': len(captured_paths)
        }
    except SyntaxError as e:
        return {
            'status': 'partial',
            'error': f'Syntax error: {e}',
            'sources': [],
            'sinks': [],
            'paths': [],
            'safe_cases': []
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'sources': [],
            'sinks': [],
            'paths': [],
            'safe_cases': []
        }


@safe
def trace_taint_flow(source_id: str, tool_context: ToolContext) -> dict:
    """Trace taint from source to sinks with provenance.

    Basic intraprocedural Python taint analysis:
    - Identifies common sources (HTTP requests, CLI input, environment variables)
    - Identifies common sinks (SQL execution, eval/exec, shell commands, file operations)
    - Tracks simple local variable assignments between source and sink
    - Returns source location, sink location, and intermediate steps
    - Includes safe-case handling (e.g., parameterized SQL)

    Status meanings:
        - ok: Analysis completed successfully (including zero findings)
        - partial: Some relevant code could not be analyzed
        - unsupported: Requested analysis not supported
        - error: Analysis failed
    """
    try:
        from ..intelligence.graph_engine.codegraph import codegraph
        from ..config import REPO_ROOT

        # Resolve component directly through CodeGraph
        graph = codegraph.load_current_graph()
        node = graph.get(source_id)

        if not node:
            return {
                'status': 'not_found',
                'source_id': source_id,
                'message': 'Component not found in graph'
            }

        file_path = node.get('file', '')
        if not file_path:
            return {
                'status': 'error',
                'error': 'Component has no file path'
            }

        # Validate file is inside REPO_ROOT
        full_file_path = REPO_ROOT / file_path
        if not full_file_path.exists():
            return {
                'status': 'error',
                'error': f'File not found in repository: {file_path}'
            }

        # Security check: ensure resolved path is still inside REPO_ROOT
        try:
            full_file_path = full_file_path.resolve()
            if not str(full_file_path).startswith(str(REPO_ROOT.resolve())):
                return {
                    'status': 'error',
                    'error': f'File path outside repository: {file_path}'
                }
        except Exception:
            return {
                'status': 'error',
                'error': f'Invalid file path: {file_path}'
            }

        if not _is_python_file(file_path):
            return {
                'status': 'unsupported',
                'message': 'Taint analysis only implemented for Python'
            }

        tree = _parse_python_ast(str(full_file_path))
        if not tree:
            return {
                'status': 'partial',
                'message': 'Could not parse file completely'
            }

        # Find the target function in the AST
        func_name = node.get('name', '')
        if not func_name and '.' in node.get('id', ''):
            func_name = node['id'].split('.')[-1]

        func_node = None
        for node_ast in ast.walk(tree):
            if isinstance(node_ast, ast.FunctionDef) and node_ast.name == func_name:
                # Match by source location if available
                node_start = node.get('start', 0)
                if node_start == 0 or node_ast.lineno == node_start:
                    func_node = node_ast
                    break

        if not func_node:
            return {
                'status': 'not_found',
                'message': f'Function {func_name} not found in AST'
            }

        # Get the line offset of the function to adjust line numbers
        line_offset = func_node.lineno - 1  # Convert to 0-based offset

        # Use the testable helper for analysis
        import ast as ast_module
        source_code = ast_module.get_source_segment(full_file_path.read_text(encoding='utf-8'), func_node)
        if not source_code:
            source_code = full_file_path.read_text(encoding='utf-8')

        analysis_result = analyze_python_taint_source(source_code, str(full_file_path))

        # Adjust line numbers in results to account for the function offset
        def adjust_line_numbers(obj):
            """Recursively adjust line numbers in the result structure."""
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key == 'line' and isinstance(value, int):
                        obj[key] = value + line_offset
                    elif isinstance(value, (dict, list)):
                        adjust_line_numbers(value)
            elif isinstance(obj, list):
                for item in obj:
                    adjust_line_numbers(item)

        # Adjust line numbers in sources, sinks, paths, and safe_cases
        adjusted_result = {
            'status': analysis_result.get('status', 'ok'),
            'source_id': source_id,
            'sources': analysis_result.get('sources', []),
            'sinks': analysis_result.get('sinks', []),
            'paths': analysis_result.get('paths', []),
            'safe_cases': analysis_result.get('safe_cases', []),
            'path_count': len(analysis_result.get('paths', []))
        }
        adjust_line_numbers(adjusted_result)

        return adjusted_result
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def visualize_data_flow(function_id: str, tool_context: ToolContext) -> dict:
    """Visualize data flow using graph emission."""
    try:
        from .visualization_spatial_tools import _emit_command
        from ..intelligence.dataflow import dfg_to_unity_format

        # Build data-flow graph
        dfg_result = build_data_flow_graph(function_id, tool_context)

        if dfg_result.get('status') != 'ok':
            return dfg_result

        # Convert to Unity format
        from ..intelligence.dataflow.models import DataFlowGraph
        dfg_dict = dfg_result['graph']
        dfg = DataFlowGraph(
            function_id=dfg_dict['function_id'],
            file=dfg_dict['file'],
        )
        # Reconstruct nodes and edges from dict
        from ..intelligence.dataflow.models import DataFlowNode, DataFlowEdge
        for node_dict in dfg_dict['nodes']:
            node = DataFlowNode(**node_dict)
            dfg.add_node(node)
        for edge_dict in dfg_dict['edges']:
            edge = DataFlowEdge(**edge_dict)
            dfg.add_edge(edge)

        unity_graph = dfg_to_unity_format(dfg)

        # Emit the graph to Unity
        _emit_command(tool_context, 'show_graph',
                     nodes=unity_graph['nodes'],
                     edges=unity_graph['edges'],
                     title=f'Data Flow: {function_id}',
                     graph_type='data_flow')

        return {
            'status': 'ok',
            'function_id': function_id,
            'node_count': len(unity_graph['nodes']),
            'edge_count': len(unity_graph['edges']),
            'graph_type': 'data_flow'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def identify_data_leaks(tool_context: ToolContext) -> dict:
    """Identify potential data leaks (sensitive data reaching sinks)."""
    try:
        from .data_flow_intelligence_tools import trace_taint_flow
        from ..intelligence.graph_engine.codegraph import codegraph
        
        graph = codegraph.load_current_graph()
        
        leaks = []
        
        # Check each function for potential leaks
        for node_id, node in graph._nodes.items():
            if node.get('level') == 'function':
                taint_result = trace_taint_flow(node_id, tool_context)
                if taint_result.get('status') == 'ok':
                    # Check if sensitive names reach sinks
                    for path in taint_result.get('paths', []):
                        sink_call = path['sink']['call']
                        if any(sensitive in sink_call.lower() for sensitive in ['log', 'print', 'request', 'http']):
                            leaks.append({
                                'function': node_id,
                                'sink': sink_call,
                                'line': path['sink']['line'],
                                'kind': 'likely'
                            })
        
        return {
            'status': 'ok',
            'leaks': leaks,
            'leak_count': len(leaks)
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def identify_data_validation_gaps(tool_context: ToolContext) -> dict:
    """Identify validation gaps (data from sources not validated before use)."""
    try:
        from .data_flow_intelligence_tools import trace_taint_flow
        from ..intelligence.graph_engine.codegraph import codegraph
        
        graph = codegraph.load_current_graph()
        
        gaps = []
        
        for node_id, node in graph._nodes.items():
            if node.get('level') == 'function':
                taint_result = trace_taint_flow(node_id, tool_context)
                if taint_result.get('status') == 'ok':
                    sources = taint_result.get('sources', [])
                    sinks = taint_result.get('sinks', [])
                    
                    # If we have sources but no validation before sinks
                    if sources and sinks:
                        gaps.append({
                            'function': node_id,
                            'sources': len(sources),
                            'sinks': len(sinks),
                            'kind': 'likely'
                        })
        
        return {
            'status': 'ok',
            'gaps': gaps,
            'gap_count': len(gaps)
        }
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

        # Python: exact call sites from the AST; other languages: textual matches
        from .navigation_tools import _python_call_sites
        from ._common import repo_root
        py_sites = _python_call_sites(function_id, repo_root())
        if py_sites:
            call_sites = [{'file': s['file'], 'line': s['line'], 'type': 'call', 'caller': s['caller']} for s in py_sites]
        else:
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
    function_id: str,
    tool_context: ToolContext
) -> dict:
    """Build data flow graphs using the new data-flow engine."""
    try:
        from ..intelligence.graph_engine.codegraph import codegraph
        from ..intelligence.dataflow.service import analyze_python_data_flow

        # Resolve the function
        graph = codegraph.load_current_graph()
        node = graph.get(function_id)

        if not node:
            return {
                'status': 'not_found',
                'function_id': function_id,
                'message': 'Function not found in graph'
            }

        file_path = node.get('file', '')
        if not file_path:
            return {
                'status': 'error',
                'error': 'Node has no file path'
            }

        if not _is_python_file(file_path):
            return {
                'status': 'not_applicable',
                'function_id': function_id,
                'message': 'Data flow analysis only implemented for Python'
            }

        # Read source code
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()

        # Call the data-flow service
        symbol = {
            'id': node.get('id'),
            'name': node.get('name'),
            'qualname': node.get('qualname'),
            'file': file_path,
            'source': source,
            'start': node.get('start'),
            'end': node.get('end'),
            'kind': node.get('kind'),
        }

        result = analyze_python_data_flow(graph, symbol)

        if 'error' in result:
            return {
                'status': 'error',
                'error': result['error'],
                'function_id': function_id,
            }

        return {
            'status': 'ok',
            'function_id': function_id,
            'graph': result['graph'].to_dict(),
            'validation': result['validation'],
            'diagnostics': result['diagnostics'],
            'metadata': result['metadata'],
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'function_id': function_id,
        }


        # Read source
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()

        # Build CFG
        cfg_builder = PythonCFGBuilder()
        cfg = cfg_builder.build_function(
            function_ast=func_node,
            function_id=node.get('id', function_id),
            source=source,
            file_path=file_path
        )

        # Extract definition/use facts
        def_use_extractor = PythonDefUseExtractor()
        facts = def_use_extractor.extract_function(
            function_ast=func_node,
            function_id=node.get('id', function_id),
            source=source
        )

        # Perform reaching definitions analysis
        reaching_analyzer = ReachingDefinitionsAnalyzer()
        analysis_result = reaching_analyzer.analyze(cfg, facts)

        # Build data-flow graph
        dfg_builder = DataFlowGraphBuilder()
        dfg = dfg_builder.build(cfg, facts, analysis_result)

        return {
            'status': 'ok',
            'function_id': function_id,
            'graph': dfg.to_dict(),
            'definition_count': len(facts.definitions),
            'use_count': len(facts.uses),
            'node_count': len(dfg.nodes),
            'edge_count': len(dfg.edges),
        }
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
