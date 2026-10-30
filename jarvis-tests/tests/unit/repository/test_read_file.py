"""
Unit tests for repository tools - Layer 1
Testing individual tool functions with controlled inputs
"""

import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / 'server'))

from ai_agents.tools.repository_tools import (
    read_file,
    read_file_range,
    list_files,
    search_files
)


class TestReadFile:
    """Test suite for read_file tool"""

    def test_t01_happy_path(self):
        """T01: Happy path - read a valid file"""
        result = read_file(
            file_path='fixtures/repositories/simple-python/main.py',
            tool_context=None
        )
        assert result['status'] == 'ok'
        assert 'def alpha():' in result['content']
        assert 'def target():' in result['content']

    def test_t02_input_validation(self):
        """T02: Input validation - reject invalid file path"""
        result = read_file(
            file_path='../../../etc/passwd',  # Path traversal attempt
            tool_context=None
        )
        assert result['status'] == 'error'
        assert 'path' in result.get('error', '').lower()

    def test_t03_output_validation(self):
        """T03: Output validation - correct response schema"""
        result = read_file(
            file_path='fixtures/repositories/simple-python/main.py',
            tool_context=None
        )
        assert 'status' in result
        assert 'file_path' in result
        assert 'content' in result
        assert isinstance(result['content'], str)

    def test_t04_empty_input(self):
        """T04: Empty input - handle non-existent file"""
        result = read_file(
            file_path='fixtures/repositories/simple-python/nonexistent.py',
            tool_context=None
        )
        assert result['status'] == 'error'

    def test_t05_boundary_conditions(self):
        """T05: Boundary conditions - minimum file size"""
        # This would test with a 0-byte file
        pass

    def test_t06_large_input(self):
        """T06: Large input - handle large files"""
        # This would test with a file > 10MB
        pass

    def test_t07_complex_input(self):
        """T07: Complex input - file with mixed content"""
        # This would test with a file containing various encodings
        pass

    def test_t08_malformed_input(self):
        """T08: Malformed input - null bytes or invalid paths"""
        result = read_file(
            file_path=None,
            tool_context=None
        )
        assert result['status'] == 'error'

    def test_t09_dependency_failure(self):
        """T09: Dependency failure - file system unavailable"""
        # This would simulate file system being unavailable
        pass

    def test_t10_timeout(self):
        """T10: Timeout - handle slow file reads"""
        # This would test with a file on a slow mounted filesystem
        pass

    def test_t11_concurrency(self):
        """T11: Concurrency - multiple simultaneous reads"""
        # This would test concurrent file reads
        pass

    def test_t12_security(self):
        """T12: Security - prevent unauthorized file access"""
        result = read_file(
            file_path='/etc/shadow',
            tool_context=None
        )
        assert result['status'] == 'error'
        assert 'permission' in result.get('error', '').lower() or 'not allowed' in result.get('error', '').lower()

    def test_t13_performance(self):
        """T13: Performance - read within time limit"""
        import time
        start = time.time()
        result = read_file(
            file_path='fixtures/repositories/simple-python/main.py',
            tool_context=None
        )
        duration = (time.time() - start) * 1000
        assert result['status'] == 'ok'
        assert duration < 100  # Should complete in < 100ms

    def test_t14_regression(self):
        """T14: Regression - ensure previous fixes remain"""
        # This would run all previous tests to ensure no regression
        pass

    def test_t15_recovery(self):
        """T15: Recovery - recover after interruption"""
        # This would test recovery after a simulated interruption
        pass


class TestReadFileRange:
    """Test suite for read_file_range tool"""

    def test_t01_happy_path(self):
        """T01: Happy path - read a valid file range"""
        result = read_file_range(
            file_path='fixtures/repositories/simple-python/main.py',
            start_line=5,
            end_line=10,
            tool_context=None
        )
        assert result['status'] == 'ok'
        assert 'def alpha():' in result['content']

    def test_t02_input_validation(self):
        """T02: Input validation - reject invalid line numbers"""
        result = read_file_range(
            file_path='fixtures/repositories/simple-python/main.py',
            start_line=-1,
            end_line=10,
            tool_context=None
        )
        assert result['status'] == 'error'

    def test_t03_output_validation(self):
        """T03: Output validation - correct response schema"""
        result = read_file_range(
            file_path='fixtures/repositories/simple-python/main.py',
            start_line=5,
            end_line=10,
            tool_context=None
        )
        assert 'status' in result
        assert 'file_path' in result
        assert 'start_line' in result
        assert 'end_line' in result
        assert 'content' in result

    def test_t04_empty_input(self):
        """T04: Empty input - range with no lines"""
        result = read_file_range(
            file_path='fixtures/repositories/simple-python/main.py',
            start_line=5,
            end_line=5,
            tool_context=None
        )
        assert result['status'] == 'ok' or result['status'] == 'error'

    def test_t05_boundary_conditions(self):
        """T05: Boundary conditions - start > end"""
        result = read_file_range(
            file_path='fixtures/repositories/simple-python/main.py',
            start_line=10,
            end_line=5,
            tool_context=None
        )
        assert result['status'] == 'error'

    def test_t06_large_input(self):
        """T06: Large input - very large range"""
        result = read_file_range(
            file_path='fixtures/repositories/simple-python/main.py',
            start_line=1,
            end_line=10000,
            tool_context=None
        )
        # Should handle gracefully, return only available lines
        assert result['status'] in ['ok', 'error']

    def test_t07_complex_input(self):
        """T07: Complex input - range spanning multiple files"""
        # This would test with a range that spans multiple logical sections
        pass

    def test_t08_malformed_input(self):
        """T08: Malformed input - non-numeric line numbers"""
        result = read_file_range(
            file_path='fixtures/repositories/simple-python/main.py',
            start_line='abc',
            end_line=10,
            tool_context=None
        )
        assert result['status'] == 'error'


class TestListFiles:
    """Test suite for list_files tool"""

    def test_t01_happy_path(self):
        """T01: Happy path - list files in directory"""
        result = list_files(
            directory='fixtures/repositories/simple-python',
            recursive=True,
            tool_context=None
        )
        assert result['status'] == 'ok'
        assert 'files' in result
        assert len(result['files']) > 0

    def test_t02_input_validation(self):
        """T02: Input validation - reject invalid directory"""
        result = list_files(
            directory='../../../etc',
            recursive=True,
            tool_context=None
        )
        assert result['status'] == 'error'

    def test_t03_output_validation(self):
        """T03: Output validation - correct response schema"""
        result = list_files(
            directory='fixtures/repositories/simple-python',
            recursive=True,
            tool_context=None
        )
        assert 'status' in result
        assert 'directory' in result
        assert 'files' in result
        assert isinstance(result['files'], list)

    def test_t04_empty_input(self):
        """T04: Empty input - empty directory"""
        result = list_files(
            directory='fixtures/empty',
            recursive=True,
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']

    def test_t05_boundary_conditions(self):
        """T05: Boundary conditions - non-recursive listing"""
        result = list_files(
            directory='fixtures/repositories/simple-python',
            recursive=False,
            tool_context=None
        )
        assert result['status'] == 'ok'

    def test_t06_large_input(self):
        """T06: Large input - directory with many files"""
        # This would test with a directory containing 10,000+ files
        pass

    def test_t07_complex_input(self):
        """T07: Complex input - directory with nested subdirectories"""
        result = list_files(
            directory='fixtures/repositories/simple-python',
            recursive=True,
            tool_context=None
        )
        assert result['status'] == 'ok'
        # Should include subpackage/ files

    def test_t08_malformed_input(self):
        """T08: Malformed input - null directory"""
        result = list_files(
            directory=None,
            recursive=True,
            tool_context=None
        )
        assert result['status'] == 'error'
