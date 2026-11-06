"""Data-flow analysis service."""
from typing import Dict, Any
from ..parsers.python_ast import parse_python_source
from ..parsers.python_symbol_locator import find_function_ast
from ..controlflow.python_cfg import PythonCFGBuilder
from ..controlflow.validator import validate_cfg
from .python_extractor import PythonDefUseExtractor
from .reaching_definitions import ReachingDefinitionsAnalyzer
from .dependency_builder import DataFlowGraphBuilder, dfg_to_unity_format


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

        tree = parse_python_source(source, file_path)

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

        # Build CFG first (required for data-flow)
        function_id = symbol.get('id') or f"{file_path}::{function_ast.name}"
        cfg_builder = PythonCFGBuilder()
        artifact = cfg_builder.build_function(
            function_ast=function_ast,
            function_id=function_id,
            source=source,
            file_path=file_path,
        )
        cfg = artifact.graph

        # Validate CFG
        cfg_validation = validate_cfg(cfg)
        if not cfg_validation['valid']:
            return {
                'error': f'CFG validation failed: {cfg_validation["errors"]}',
                'graph': None,
                'cfg': cfg,
                'validation': cfg_validation,
                'diagnostics': cfg.metadata.get('diagnostics', []),
                'metadata': {},
            }

        # Extract definition/use facts using the CFG artifact
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
                'error': analysis_result['error'],
                'graph': None,
                'cfg': cfg,
                'validation': {'valid': False, 'errors': [analysis_result['error']], 'warnings': []},
                'diagnostics': analysis_result.get('diagnostics', []),
                'metadata': {},
            }

        # Build data-flow graph
        dfg_builder = DataFlowGraphBuilder()
        dfg = dfg_builder.build(cfg, facts, analysis_result)

        # Validate DFG
        dfg_validation = dfg_builder.validate_dataflow_graph(cfg, facts, dfg)

        return {
            'graph': dfg,
            'cfg': cfg,
            'validation': dfg_validation,
            'diagnostics': facts.diagnostics + analysis_result.get('diagnostics', []),
            'metadata': {
                'language': 'python',
                'scope': 'intra_function',
                'function_name': function_ast.name,
                'function_id': function_id,
                'definition_count': len(facts.definitions),
                'use_count': len(facts.uses),
                'operation_count': len(facts.operations),
            },
        }

    except Exception as e:
        return {
            'error': str(e),
            'graph': None,
            'cfg': None,
            'validation': {'valid': False, 'errors': [str(e)], 'warnings': []},
            'diagnostics': [],
            'metadata': {},
        }
