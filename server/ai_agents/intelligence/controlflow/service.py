"""Control-flow analysis service."""
from typing import Dict, Any
from ..parsers.python_ast import parse_python_source
from ..parsers.python_symbol_locator import find_function_ast
from .python_cfg import PythonCFGBuilder
from .validator import validate_cfg
from .graph_builder import cfg_to_unity_format


def analyze_python_control_flow(
    graph: Dict[str, Any],
    symbol: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Analyze control flow for a Python function.

    Args:
        graph: The repository graph (may be None for standalone analysis)
        symbol: The symbol information for the function to analyze

    Returns:
        Analysis result containing:
        - graph: ControlFlowGraph object
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
                'validation': {'valid': False, 'errors': ['No source code'], 'warnings': []},
                'diagnostics': [],
                'metadata': {},
            }

        tree = parse_python_source(source, file_path)

        # Find the function AST node
        function_ast = find_function_ast(tree, symbol)
        if not function_ast:
            return {
                'error': f'Function not found: {symbol.get("name")}',
                'graph': None,
                'validation': {'valid': False, 'errors': ['Function not found'], 'warnings': []},
                'diagnostics': [],
                'metadata': {},
            }

        # Build CFG
        function_id = symbol.get('id') or f"{file_path}::{function_ast.name}"
        builder = PythonCFGBuilder()
        artifact = builder.build_function(
            function_ast=function_ast,
            function_id=function_id,
            source=source,
            file_path=file_path,
        )
        cfg = artifact.graph

        # Validate CFG
        validation = validate_cfg(cfg)
        
        # Do not return invalid graphs as successful
        if not validation['valid']:
            return {
                'error': f'CFG validation failed: {validation["errors"]}',
                'graph': cfg,
                'validation': validation,
                'diagnostics': cfg.metadata.get('diagnostics', []),
                'metadata': {
                    'language': 'python',
                    'scope': 'intra_function',
                    'function_name': function_ast.name,
                    'function_id': function_id,
                },
            }

        return {
            'graph': cfg,
            'validation': validation,
            'diagnostics': cfg.metadata.get('diagnostics', []),
            'metadata': {
                'language': 'python',
                'scope': 'intra_function',
                'function_name': function_ast.name,
                'function_id': function_id,
            },
        }

    except Exception as e:
        return {
            'error': str(e),
            'graph': None,
            'validation': {'valid': False, 'errors': [str(e)], 'warnings': []},
            'diagnostics': [],
            'metadata': {},
        }
