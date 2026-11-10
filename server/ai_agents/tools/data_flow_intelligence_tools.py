"""
Agent 6 - Data Flow Intelligence Tools
Understand how data moves through the entire application.
"""

from typing import Optional, List, Dict, Any
from google.adk.tools import ToolContext
from ._safe import safe
from ._common import abs_repo_path
import ast


def _is_python_file(file_path: str) -> bool:
    return file_path.endswith('.py')


def _parse_python_ast(file_path: str) -> Optional[ast.AST]:
    try:
        content = abs_repo_path(file_path).read_text(encoding='utf-8')
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
        with open(abs_repo_path(file_path), 'r', encoding='utf-8') as f:
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
        with open(abs_repo_path(file_path), 'r', encoding='utf-8') as f:
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

