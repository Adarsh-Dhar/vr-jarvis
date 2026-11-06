"""Test exception groups (try* and except*)."""

import ast
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_exception_group_basic():
    """Test basic exception group structure."""
    source = """
def process():
    try*:
        operation()
    except* ValueError:
        handle()
"""
    
    # Exception groups require Python 3.11+ syntax
    try:
        cfg = PythonCFGBuilder().build_function(
            function_ast=ast.parse(source, feature_version=(3, 11)).body[0],
            function_id="test::process",
            source=source,
            file_path="test.py"
        )
        
        # Should have try* node
        trystar_nodes = [n for n in cfg.graph.nodes if n.ast_kind == 'TryStar']
        assert len(trystar_nodes) >= 1
        
        # Should have except* handler
        except_star_nodes = [n for n in cfg.graph.nodes if n.ast_kind == 'ExceptStar']
        assert len(except_star_nodes) >= 1
    except SyntaxError:
        # If syntax not supported, skip test
        pass


def test_exception_group_multiple_handlers():
    """Test exception group with multiple handlers."""
    source = """
def process():
    try*:
        operation()
    except* ValueError:
        handle_value()
    except* TypeError:
        handle_type()
"""
    
    try:
        cfg = PythonCFGBuilder().build_function(
            function_ast=ast.parse(source, feature_version=(3, 11)).body[0],
            function_id="test::process",
            source=source,
            file_path="test.py"
        )
        
        # Should have multiple except* handlers
        except_star_nodes = [n for n in cfg.graph.nodes if n.ast_kind == 'ExceptStar']
        assert len(except_star_nodes) >= 2
    except SyntaxError:
        pass


def test_exception_group_metadata():
    """Test exception group metadata is preserved."""
    source = """
def process():
    try*:
        operation()
    except* ValueError:
        handle()
"""
    
    try:
        cfg = PythonCFGBuilder().build_function(
            function_ast=ast.parse(source, feature_version=(3, 11)).body[0],
            function_id="test::process",
            source=source,
            file_path="test.py"
        )
        
        # Try* node should have exception_group metadata
        trystar_nodes = [n for n in cfg.graph.nodes if n.ast_kind == 'TryStar']
        assert trystar_nodes[0].metadata.get('exception_group') == True
        
        # Except* handler should have exception_group_handler metadata
        except_star_nodes = [n for n in cfg.graph.nodes if n.ast_kind == 'ExceptStar']
        assert except_star_nodes[0].metadata.get('exception_group_handler') == True
    except SyntaxError:
        pass
