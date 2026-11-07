"""Control-flow analysis service."""
from typing import Dict, Any
from ..parsers.python_ast import parse_python_module
from ..parsers.python_symbol_locator import find_function_ast
from .python_cfg import PythonCFGBuilder
from .validator import validate_cfg
from .graph_builder import cfg_to_unity_format
from ..dataflow.graph_persistence import GraphPersistenceManager


# Global persistence manager instance
_persistence_manager = GraphPersistenceManager()


def analyze_python_control_flow(
    graph: Dict[str, Any],
    symbol: Dict[str, Any],
    use_cache: bool = True
) -> Dict[str, Any]:
    """
    Analyze control flow for a Python function with optional caching.

    Args:
        graph: The repository graph (may be None for standalone analysis)
        symbol: The symbol information for the function to analyze
        use_cache: Whether to use cached results (default True)

    Returns:
        Analysis result containing:
        - graph: ControlFlowGraph object
        - validation: Validation result
        - diagnostics: List of diagnostic messages
        - metadata: Analysis metadata
        - cached: Whether the result was from cache
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
                'cached': False,
            }

        tree = parse_python_module(source, file_path)

        # Find the function AST node
        function_ast = find_function_ast(tree, symbol)
        if not function_ast:
            return {
                'error': f'Function not found: {symbol.get("name")}',
                'graph': None,
                'validation': {'valid': False, 'errors': ['Function not found'], 'warnings': []},
                'diagnostics': [],
                'metadata': {},
                'cached': False,
            }

        # Build CFG
        function_id = symbol.get('id') or f"{file_path}::{function_ast.name}"

        # Check cache if enabled
        if use_cache:
            cached_entry = _persistence_manager.get_cached_graph(function_id)
            if cached_entry:
                # Validate cache against current source
                cfg_dict = {
                    'nodes': [{'id': 'placeholder'}],  # Placeholder for validation
                    'edges': []
                }
                if _persistence_manager.is_cache_valid(function_id, source, cfg_dict, cfg_dict, {}):
                    return {
                        'graph': None,  # Cached graphs need to be reconstructed
                        'validation': {'valid': True, 'errors': [], 'warnings': []},
                        'diagnostics': [],
                        'metadata': {
                            'language': 'python',
                            'scope': 'intra_function',
                            'function_name': function_ast.name,
                            'function_id': function_id,
                        },
                        'cached': True,
                        'cache_entry': cached_entry,
                    }

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
                'cached': False,
            }

        # Cache the result
        cfg_dict = cfg.to_dict()
        _persistence_manager.cache_graph(
            function_id=function_id,
            source=source,
            cfg=cfg_dict,
            dfg={'nodes': [], 'edges': []},  # No DFG in CFG analysis
            callee_hashes={}
        )

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
            'cached': False,
        }

    except Exception as e:
        return {
            'error': str(e),
            'graph': None,
            'validation': {'valid': False, 'errors': [str(e)], 'warnings': []},
            'diagnostics': [],
            'metadata': {},
            'cached': False,
        }


def invalidate_control_flow_cache(function_id: str):
    """Invalidate cached control flow for a function."""
    _persistence_manager.invalidate_function(function_id)
