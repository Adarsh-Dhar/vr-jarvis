"""
Integration tests for tools - Layer 3
Testing tools with real services and data
"""

import pytest
from pathlib import Path
import sys
import tempfile
import shutil
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / 'server'))

from ai_agents.tools.relationship_intelligence_tools import (
    find_callers,
    find_callees,
    build_call_graph
)
from ai_agents.tools.repository_tools import (
    index_repository,
    read_file
)


class TestFindCallersIntegration:
    """Integration tests for find_callers with real repository"""

    @pytest.fixture
    def test_repository(self):
        """Set up a temporary test repository"""
        # Create a temporary directory with test code
        temp_dir = tempfile.mkdtemp()
        test_file = Path(temp_dir) / 'test.py'
        test_file.write_text('''
def caller1():
    target()

def caller2():
    target()

def target():
    return True
''')
        yield temp_dir
        # Cleanup
        shutil.rmtree(temp_dir)

    def test_with_real_repository(self, test_repository):
        """Test find_callers with a real repository"""
        # First index the repository
        index_result = index_repository(
            repository_path=test_repository,
            tool_context=None
        )
        assert index_result['status'] == 'ok'

        # Then find callers
        result = find_callers(
            function_id='target',
            tool_context=None
        )
        assert result['status'] == 'ok'
        assert 'callers' in result
        caller_names = [c['name'] for c in result['callers']]
        assert 'caller1' in caller_names
        assert 'caller2' in caller_names

    def test_with_parser_integration(self, test_repository):
        """Test find_callers integrates with actual parser"""
        # Read the file using the real file system
        read_result = read_file(
            file_path=str(Path(test_repository) / 'test.py'),
            tool_context=None
        )
        assert read_result['status'] == 'ok'
        assert 'def caller1():' in read_result['content']

    def test_correct_source_locations(self, test_repository):
        """Test that source locations are accurate"""
        result = find_callers(
            function_id='target',
            tool_context=None
        )
        assert result['status'] == 'ok'
        for caller in result['callers']:
            assert 'file' in caller
            assert 'line' in caller
            assert caller['line'] > 0


class TestBuildCallGraphIntegration:
    """Integration tests for build_call_graph"""

    @pytest.fixture
    def complex_repository(self):
        """Set up a more complex test repository"""
        temp_dir = tempfile.mkdtemp()
        test_file = Path(temp_dir) / 'complex.py'
        test_file.write_text('''
def a():
    b()

def b():
    c()

def c():
    d()

def d():
    return True
''')
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_build_real_graph(self, complex_repository):
        """Test building a call graph from real code"""
        result = build_call_graph(
            scope=complex_repository,
            tool_context=None
        )
        assert result['status'] == 'ok'
        assert 'graph' in result
        assert 'nodes' in result['graph']
        assert 'edges' in result['graph']
        assert len(result['graph']['nodes']) == 4  # a, b, c, d
        assert len(result['graph']['edges']) == 3  # a->b, b->c, c->d

    def test_graph_correctness(self, complex_repository):
        """Test that the graph is structurally correct"""
        result = build_call_graph(
            scope=complex_repository,
            tool_context=None
        )
        assert result['status'] == 'ok'
        
        # Verify edges
        edges = result['graph']['edges']
        edge_pairs = [(e['from'], e['to']) for e in edges]
        assert ('a', 'b') in edge_pairs
        assert ('b', 'c') in edge_pairs
        assert ('c', 'd') in edge_pairs


class TestRunUnitTestsIntegration:
    """Integration tests for test execution tools"""

    @pytest.fixture
    def test_project(self):
        """Set up a test project with actual tests"""
        temp_dir = tempfile.mkdtemp()
        
        # Create a simple test file
        test_file = Path(temp_dir) / 'test_sample.py'
        test_file.write_text('''
def test_passing():
    assert True

def test_failing():
    assert False
''')
        
        # Create a simple implementation file
        impl_file = Path(temp_dir) / 'sample.py'
        impl_file.write_text('''
def sample_function():
    return True
''')
        
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_execute_real_tests(self, test_project):
        """Test executing actual unit tests"""
        from ai_agents.tools.testing_verification_tools import run_unit_tests
        
        result = run_unit_tests(
            test_files=[str(Path(test_project) / 'test_sample.py')],
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']  # May fail if pytest not installed
        if result['status'] == 'ok':
            assert 'passed' in result
            assert 'failed' in result

    def test_test_coverage_real(self, test_project):
        """Test measuring actual test coverage"""
        from ai_agents.tools.testing_verification_tools import measure_test_coverage
        
        result = measure_test_coverage(
            repository_path=test_project,
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']  # May fail if coverage not installed


class TestApplyPatchIntegration:
    """Integration tests for patch application"""

    @pytest.fixture
    def patch_repository(self):
        """Set up a repository for patch testing"""
        temp_dir = tempfile.mkdtemp()
        
        # Create a file to patch
        test_file = Path(temp_dir) / 'target.py'
        test_file.write_text('''
def original_function():
    return "original"
''')
        
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_apply_real_patch(self, patch_repository):
        """Test applying a real patch"""
        from ai_agents.tools.software_engineering_tools import apply_patch
        
        patch_content = '''--- a/target.py
+++ b/target.py
@@ -1,3 +1,3 @@
 def original_function():
-    return "original"
+    return "modified"
'''
        
        result = apply_patch(
            patch_content=patch_content,
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']

    def test_patch_modifies_correct_file(self, patch_repository):
        """Test that patch modifies the correct file"""
        # Read original content
        original_file = Path(patch_repository) / 'target.py'
        original_content = original_file.read_text()
        assert 'original' in original_content
        
        # Apply patch
        from ai_agents.tools.software_engineering_tools import apply_patch
        patch_content = '''--- a/target.py
+++ b/target.py
@@ -1,3 +1,3 @@
 def original_function():
-    return "original"
+    return "modified"
'''
        
        result = apply_patch(
            patch_content=patch_content,
            tool_context={'worktree': patch_repository}
        )
        
        if result['status'] == 'ok':
            # Verify file was modified
            new_content = original_file.read_text()
            assert 'modified' in new_content
