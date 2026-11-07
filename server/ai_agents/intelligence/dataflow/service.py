"""Data-flow analysis service."""
from typing import Dict, Any, Optional
import ast
from ..parsers.python_ast import parse_python_module
from ..parsers.python_symbol_locator import find_function_ast
from ..controlflow.python_cfg import PythonCFGBuilder
from ..controlflow.validator import validate_cfg
from .python_extractor import PythonDefUseExtractor
from .reaching_definitions import ReachingDefinitionsAnalyzer
from .dependency_builder import DataFlowGraphBuilder, dfg_to_unity_format
from .validator import validate_dfg


def _analyze_python_data_flow_core(
    source: str,
    file_path: str,
    function_ast: ast.FunctionDef,
    function_id: str,
    cfg: Optional[object] = None
) -> Dict[str, Any]:
    """
    Core DFG analysis pipeline shared by both public service methods.
    
    Args:
        source: Source code containing the function
        file_path: Path to the source file
        function_ast: The function AST node
        function_id: Unique function identifier
        cfg: Optional pre-built CFG (if already available)
    
    Returns:
        Analysis result with status, DFG, CFG, validation, and metadata
    """
    # Build CFG if not provided
    if cfg is None:
        cfg_builder = PythonCFGBuilder()
        artifact = cfg_builder.build_function(
            function_ast=function_ast,
            function_id=function_id,
            source=source,
            file_path=file_path,
        )
        cfg = artifact.graph
    else:
        # If CFG provided, create minimal artifact for extractor
        from .controlflow.models import CFGBuildArtifact, ASTCFGIndex
        artifact = CFGBuildArtifact(
            graph=cfg,
            ast_index=ASTCFGIndex(),
            function_ast=function_ast,
        )
    
    # Validate CFG
    cfg_validation = validate_cfg(cfg)
    if not cfg_validation['valid']:
        return {
            'status': 'error',
            'error': f'CFG validation failed: {cfg_validation["errors"]}',
            'cfg': cfg,
            'graph': None,
            'validation': cfg_validation,
            'diagnostics': cfg.metadata.get('diagnostics', []),
            'metadata': {},
        }
    
    # Extract definition/use facts
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path=file_path,
    )
    
    # Perform reaching-definitions analysis
    analyzer = ReachingDefinitionsAnalyzer()
    analysis_result = analyzer.analyze(cfg, facts)
    
    if 'error' in analysis_result:
        return {
            'status': 'error',
            'error': analysis_result['error'],
            'cfg': cfg,
            'graph': None,
            'validation': {'valid': False, 'errors': [analysis_result['error']], 'warnings': []},
            'diagnostics': analysis_result.get('diagnostics', []),
            'metadata': {},
        }
    
    # Build data-flow graph
    dfg_builder = DataFlowGraphBuilder()
    dfg = dfg_builder.build(cfg, facts, analysis_result)
    
    # Validate DFG with strict validator
    dfg_validation = validate_dfg(dfg=dfg, facts=facts, cfg=cfg)
    
    # Do not return invalid DFG as successful
    if not dfg_validation['valid']:
        return {
            'status': 'error',
            'error': f'DFG validation failed: {dfg_validation["errors"]}',
            'cfg': cfg,
            'graph': None,
            'validation': dfg_validation,
            'diagnostics': facts.diagnostics + analysis_result.get('diagnostics', []),
            'metadata': {},
        }
    
    # Determine status based on validation warnings
    status = 'success'
    if dfg_validation.get('warnings'):
        status = 'success_with_warnings'
    if cfg_validation.get('warnings'):
        status = 'success_with_warnings'
    
    # M7: Verify service result consistency - preserve all required fields
    return {
        'status': status,
        'cfg': cfg,
        'graph': dfg,
        'validation': dfg_validation,
        'diagnostics': facts.diagnostics + analysis_result.get('diagnostics', []),
        'metadata': {
            'language': 'python',
            'scope': 'intra_function',
            'function_name': function_ast.name,
            'function_id': function_id,
            'file_path': file_path,
            'definition_count': len(facts.definitions),
            'use_count': len(facts.uses),
            'operation_count': len(facts.operations),
        },
    }


def analyze_python_data_flow_simple(
    function_name: str,
    source: str,
    file_path: str
) -> Dict[str, Any]:
    """
    Simplified interface for DFG analysis (used by agent tools).
    
    Args:
        function_name: Name of the function to analyze
        source: Source code containing the function
        file_path: Path to the source file
        
    Returns:
        Analysis result with status, DFG nodes/edges, and metadata
    """
    try:
        # Parse source
        tree = parse_python_module(source, file_path)

        # Find function AST using the proper locator
        symbol = {
            'name': function_name,
            'qualname': function_name,  # Use the same as name for simple interface
            'file': file_path,
        }
        function_ast = find_function_ast(tree, symbol)

        if not function_ast:
            return {
                'status': 'error',
                'error': f'Function not found: {function_name}'
            }
        
        # Handle both FunctionDef and AsyncFunctionDef
        if not isinstance(function_ast, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return {
                'status': 'error',
                'error': f'Found symbol is not a function: {type(function_ast).__name__}'
            }
        
        # Build function ID
        function_id = f"{file_path}::{function_name}"
        
        # Call the canonical core analysis
        result = _analyze_python_data_flow_core(
            source=source,
            file_path=file_path,
            function_ast=function_ast,
            function_id=function_id,
        )
        
        # If core analysis failed, return early
        if result['status'] == 'error':
            return result
        
        # Convert to Unity format for simple interface
        unity_format = dfg_to_unity_format(result['graph'])
        
        # Add Unity-format specific fields
        result['dfg_nodes'] = unity_format.get('nodes', [])
        result['dfg_edges'] = unity_format.get('edges', [])
        result['graph_type'] = unity_format.get('graph_type', 'data_flow')
        result['function_name'] = function_name
        result['cfg_references'] = {
            'function_id': function_id,
            'entry_node_id': result['cfg'].entry_node_id,
            'exit_node_id': result['cfg'].exit_node_id,
        }
        
        return result
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


def analyze_python_data_flow(
    graph: Dict[str, Any],
    symbol: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Analyze data flow for a Python function.

    This builds the CFG first, then uses it for data-flow extraction
    and reaching-definitions analysis.

    Args:
        graph: The repository graph (may be None for standalone analysis)
        symbol: The symbol information for the function to analyze

    Returns:
        Analysis result containing:
        - graph: DataFlowGraph object
        - cfg: ControlFlowGraph object (for reference)
        - validation: Validation result
        - diagnostics: List of diagnostic messages
        - metadata: Analysis metadata
    """
    try:
        # Parse the source file
        file_path = symbol.get('file')
        source = symbol.get('source') or ''

        if not source:
            return {
                'error': 'No source code available',
                'graph': None,
                'cfg': None,
                'validation': {'valid': False, 'errors': ['No source code'], 'warnings': []},
                'diagnostics': [],
                'metadata': {},
            }

        tree = parse_python_module(source, file_path)

        # Find the function AST node
        function_ast = find_function_ast(tree, symbol)
        if not function_ast:
            return {
                'error': f'Function not found: {symbol.get("name")}',
                'graph': None,
                'cfg': None,
                'validation': {'valid': False, 'errors': ['Function not found'], 'warnings': []},
                'diagnostics': [],
                'metadata': {},
            }
        
        # Handle both FunctionDef and AsyncFunctionDef
        if not isinstance(function_ast, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return {
                'error': f'Found symbol is not a function: {type(function_ast).__name__}',
                'graph': None,
                'cfg': None,
                'validation': {'valid': False, 'errors': ['Not a function'], 'warnings': []},
                'diagnostics': [],
                'metadata': {},
            }

        # Build function ID
        function_id = symbol.get('id') or f"{file_path}::{function_ast.name}"
        
        # Call the canonical core analysis
        result = _analyze_python_data_flow_core(
            source=source,
            file_path=file_path,
            function_ast=function_ast,
            function_id=function_id,
        )
        
        # Add graph parameter back for compatibility (unused in core)
        result['graph'] = result.pop('graph', None)
        
        return result

    except Exception as e:
        return {
            'error': str(e),
            'graph': None,
            'cfg': None,
            'validation': {'valid': False, 'errors': [str(e)], 'warnings': []},
            'diagnostics': [],
            'metadata': {},
        }
