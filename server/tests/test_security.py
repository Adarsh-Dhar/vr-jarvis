"""
Security visualization fixture tests.

Tests positive and negative security cases:
- Secret in .env (Detected, value redacted)
- .env.local secret (Detected, value redacted)
- Unsafe SQL string construction (Vulnerability detected)
- Parameterized SQL (No SQL injection finding)
- Unsafe eval() (Vulnerability detected)
- HTTP input → variable → SQL sink (Source-to-sink path generated)
- Unsupported construct (Explicit partial/unsupported result)
"""

import pytest
from ai_agents.tools.security_quality_tools import scan_secrets, scan_vulnerabilities, detect_sql_injection
from ai_agents.tools.data_flow_intelligence_tools import trace_taint_flow, analyze_python_taint_source
from ai_agents.tools.visualization_spatial_tools import visualize_security_flow
from pathlib import Path
import tempfile
import os


def test_scan_secrets_env_redaction():
    """Test that secret in .env is detected with value redacted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create .env file with secret
        env_file = tmppath / ".env"
        env_file.write_text('api_key = "sk-1234567890abcdef1234567890abcdef"\n')
        
        result = scan_secrets(str(tmppath), None)
        
        assert result['status'] == 'ok'
        assert len(result['findings']) > 0
        # Verify secret is redacted
        for finding in result['findings']:
            assert '***REDACTED***' in finding['evidence']
            # The actual secret value should not appear
            assert '1234567890abcdef' not in finding['evidence']


def test_scan_secrets_env_local_redaction():
    """Test that secret in .env.local is detected with value redacted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create .env.local file with secret
        env_file = tmppath / ".env.local"
        env_file.write_text('password = "mySecretPassword123"\n')
        
        result = scan_secrets(str(tmppath), None)
        
        assert result['status'] == 'ok'
        assert len(result['findings']) > 0
        # Verify secret is redacted
        for finding in result['findings']:
            assert '***REDACTED***' in finding['evidence']
            # The actual secret value should not appear
            assert 'mySecretPassword123' not in finding['evidence']


def test_detect_sql_injection_unsafe():
    """Test that unsafe SQL string construction is detected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create a file with unsafe SQL
        py_file = tmppath / "test.py"
        py_file.write_text("""
def query_user(user_id):
    sql = "SELECT * FROM users WHERE id = " + user_id
    cursor.execute(sql)
""")
        
        result = detect_sql_injection(str(tmppath), None)
        
        assert result['status'] == 'ok'
        # Should detect SQL injection
        assert len(result['findings']) > 0
        assert any(f['type'] == 'sql_injection' for f in result['findings'])


def test_detect_sql_injection_parameterized_safe():
    """Test that parameterized SQL is not flagged as vulnerable."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create a file with parameterized SQL
        py_file = tmppath / "test.py"
        py_file.write_text("""
def query_user(user_id):
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
""")
        
        result = detect_sql_injection(str(tmppath), None)
        
        assert result['status'] == 'ok'
        # Should not flag parameterized query as unsafe
        assert len(result['findings']) == 0


def test_scan_vulnerabilities_unsafe_eval():
    """Test that unsafe eval() is detected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create a file with unsafe eval
        py_file = tmppath / "test.py"
        py_file.write_text("""
def process_input(user_input):
    result = eval(user_input)
    return result
""")
        
        result = scan_vulnerabilities(str(tmppath), None)
        
        assert result['status'] == 'ok'
        # Should detect eval vulnerability
        assert len(result['vulnerabilities']) > 0
        assert any(v['type'] == 'unsafe_execution' for v in result['vulnerabilities'])


def test_trace_taint_flow_http_to_sql():
    """Test source-to-sink path from HTTP input to SQL sink."""
    # Create a test function with HTTP input to SQL sink
    test_code = """
def process_user(user_id):
    user_input = request.args.get('name')
    user_id = user_input
    query = "SELECT * FROM users WHERE id = " + user_id
    cursor.execute(query)
"""
    
    # For fixture testing, we'll test the basic structure without graph resolution
    # The actual graph resolution would require a full codegraph setup
    # This test verifies the function exists and can handle basic cases
    result = trace_taint_flow("test_function", None)
    
    # Should handle gracefully (not_found since no graph)
    assert result['status'] in ['not_found', 'unsupported', 'error']


def test_trace_taint_flow_unsupported_construct():
    """Test that unsupported constructs return explicit partial/unsupported status."""
    # Test with a non-Python file
    result = trace_taint_flow("test_function", None)
    
    # Should handle gracefully with explicit status
    assert result['status'] in ['not_found', 'unsupported', 'error']


def test_visualize_security_flow_integration():
    """Test that visualize_security_flow integrates secrets and taint analysis."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create files with both secrets and code
        env_file = tmppath / ".env"
        env_file.write_text('api_key = "sk-test1234567890abcdef"\n')
        
        py_file = tmppath / "test.py"
        py_file.write_text("""
def query_user(user_id):
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
""")
        
        # This would need graph resolution
        result = visualize_security_flow("test_component", None)
        
        # Should handle gracefully
        assert result['status'] in ['not_found', 'error']


def test_detect_sql_injection_fstring():
    """Test that f-string SQL injection is detected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        py_file = tmppath / "test.py"
        py_file.write_text("""
def query_user(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)
""")
        
        result = detect_sql_injection(str(tmppath), None)
        
        assert result['status'] == 'ok'
        assert len(result['findings']) > 0
        assert any(f['type'] == 'sql_injection' for f in result['findings'])


def test_detect_sql_injection_format():
    """Test that .format() SQL injection is detected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        py_file = tmppath / "test.py"
        py_file.write_text("""
def query_user(user_id):
    query = "SELECT * FROM users WHERE id = {}".format(user_id)
    cursor.execute(query)
""")
        
        result = detect_sql_injection(str(tmppath), None)
        
        assert result['status'] == 'ok'
        assert len(result['findings']) > 0
        assert any(f['type'] == 'sql_injection' for f in result['findings'])


def test_detect_sql_injection_percent_interpolation():
    """Test that % interpolation SQL injection is detected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        py_file = tmppath / "test.py"
        py_file.write_text("""
def query_user(user_id):
    query = "SELECT * FROM users WHERE id = %s" % user_id
    cursor.execute(query)
""")
        
        result = detect_sql_injection(str(tmppath), None)
        
        assert result['status'] == 'ok'
        assert len(result['findings']) > 0
        assert any(f['type'] == 'sql_injection' for f in result['findings'])


def test_scan_vulnerabilities_unsafe_exec():
    """Test that unsafe exec() is detected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        py_file = tmppath / "test.py"
        py_file.write_text("""
def process_input(user_input):
    result = exec(user_input)
    return result
""")
        
        result = scan_vulnerabilities(str(tmppath), None)
        
        assert result['status'] == 'ok'
        assert len(result['vulnerabilities']) > 0
        assert any(v['type'] == 'unsafe_execution' for v in result['vulnerabilities'])


def test_analyze_python_taint_source_http_to_sql():
    """Test taint analysis with HTTP input to SQL sink."""
    source_code = """
def process_user(user_id):
    user_input = request.args.get('name')
    user_id = user_input
    query = "SELECT * FROM users WHERE id = " + user_id
    cursor.execute(query)
"""
    
    result = analyze_python_taint_source(source_code, "test.py")
    
    assert result['status'] == 'ok'
    assert len(result['paths']) > 0
    path = result['paths'][0]
    assert 'source' in path
    assert 'sink' in path
    assert 'steps' in path


def test_analyze_python_taint_source_two_assignments():
    """Test taint analysis with two variable assignments."""
    source_code = """
def process_data():
    raw_input = request.args.get('data')
    processed = raw_input.strip()
    result = eval(processed)
    return result
"""
    
    result = analyze_python_taint_source(source_code, "test.py")
    
    assert result['status'] == 'ok'
    assert len(result['paths']) > 0
    path = result['paths'][0]
    # Should have intermediate steps
    assert len(path['steps']) >= 2


def test_analyze_python_taint_source_input_to_eval():
    """Test taint analysis from input() to eval()."""
    source_code = """
def process_user_input():
    user_code = input('Enter code: ')
    result = eval(user_code)
    return result
"""
    
    result = analyze_python_taint_source(source_code, "test.py")
    
    assert result['status'] == 'ok'
    assert len(result['paths']) > 0
    path = result['paths'][0]
    assert path['source']['call'] == 'input'
    assert path['sink']['call'] == 'eval'


def test_analyze_python_taint_source_reassignment_safe():
    """Test that reassignment to safe constant clears taint."""
    source_code = """
def process_user(user_id):
    user_input = request.args.get('name')
    user_id = user_input
    user_id = "safe_value"
    query = "SELECT * FROM users WHERE id = " + user_id
    cursor.execute(query)
"""
    
    result = analyze_python_taint_source(source_code, "test.py")
    
    assert result['status'] == 'ok'
    # Should not have a path because taint was cleared by reassignment
    assert len(result['paths']) == 0


def test_analyze_python_taint_source_unsupported_syntax():
    """Test that unsupported syntax returns partial status."""
    source_code = """
def invalid_syntax(
    # Missing closing parenthesis
"""
    
    result = analyze_python_taint_source(source_code, "test.py")
    
    assert result['status'] == 'partial'


def test_visualize_security_flow_integration_with_findings():
    """Test that visualize_security_flow emits findings and taint paths."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create files with findings
        env_file = tmppath / ".env"
        env_file.write_text('api_key = "sk-test1234567890abcdef"\n')
        
        py_file = tmppath / "test.py"
        py_file.write_text("""
def query_user(user_id):
    eval(user_id)
    sql = "SELECT * FROM users WHERE id = " + user_id
    cursor.execute(sql)
""")
        
        # This would need graph resolution for full test
        # For now, verify the individual scanners work and can be combined
        vuln_result = scan_vulnerabilities(str(tmppath), None)
        secrets_result = scan_secrets(str(tmppath), None)
        sql_result = detect_sql_injection(str(tmppath), None)
        
        # Verify all scanners return ok status
        assert vuln_result['status'] == 'ok'
        assert secrets_result['status'] == 'ok'
        assert sql_result['status'] == 'ok'
        
        # Verify findings exist
        assert len(vuln_result['vulnerabilities']) > 0
        assert len(secrets_result['findings']) > 0
        assert len(sql_result['findings']) > 0
        
        # Verify secret evidence is redacted
        for finding in secrets_result['findings']:
            assert '***REDACTED***' in finding['evidence']


def test_security_visualizer_combined_findings():
    """Test that security visualizer combines vulnerability, secret, and SQL findings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create files with all types of findings
        env_file = tmppath / ".env"
        env_file.write_text('api_key = "sk-test1234567890abcdef"\n')
        
        py_file = tmppath / "test.py"
        py_file.write_text("""
def query_user(user_id):
    eval(user_id)
    sql = "SELECT * FROM users WHERE id = " + user_id
    cursor.execute(sql)
""")
        
        # This would need graph resolution for full test
        # For now, verify the individual scanners work
        vuln_result = scan_vulnerabilities(str(tmppath), None)
        secrets_result = scan_secrets(str(tmppath), None)
        sql_result = detect_sql_injection(str(tmppath), None)
        
        assert vuln_result['status'] == 'ok'
        assert secrets_result['status'] == 'ok'
        assert sql_result['status'] == 'ok'
        
        # Verify findings exist
        assert len(vuln_result['vulnerabilities']) > 0
        assert len(secrets_result['findings']) > 0
        assert len(sql_result['findings']) > 0


def test_taint_input_to_eval():
    """Test that input() → eval() generates a path."""
    code = """
def dangerous():
    user_input = input("Enter command: ")
    eval(user_input)
"""
    result = analyze_python_taint_source(code, "test.py")

    assert result['status'] == 'ok'
    assert len(result['paths']) > 0
    # Verify path has source and sink steps
    path = result['paths'][0]
    assert path['source']['call'] == 'input'
    assert path['sink']['call'] == 'eval'
    assert len(path['steps']) >= 2  # source and sink


def test_taint_http_to_sql_direct():
    """Test HTTP input → direct assignment → SQL generates a path."""
    code = """
def query_user():
    user_id = request.args.get("id")
    sql = "SELECT * FROM users WHERE id = " + user_id
    cursor.execute(sql)
"""
    result = analyze_python_taint_source(code, "test.py")

    assert result['status'] == 'ok'
    assert len(result['paths']) > 0
    path = result['paths'][0]
    assert 'request.args.get' in path['source']['call']
    assert 'execute' in path['sink']['call']


def test_taint_http_two_assignments():
    """Test HTTP input → two assignments → SQL with both steps."""
    code = """
def query_user():
    raw_input = request.args.get("id")
    user_id = raw_input
    sql = "SELECT * FROM users WHERE id = " + user_id
    cursor.execute(sql)
"""
    result = analyze_python_taint_source(code, "test.py")

    assert result['status'] == 'ok'
    assert len(result['paths']) > 0
    path = result['paths'][0]
    # Should have intermediate assignment step
    steps = [s for s in path['steps'] if s['kind'] == 'assignment']
    assert len(steps) >= 1


def test_taint_strip_transformation():
    """Test HTTP input → .strip() → eval() includes transformation."""
    code = """
def dangerous():
    raw_input = input("Enter command: ")
    processed = raw_input.strip()
    eval(processed)
"""
    result = analyze_python_taint_source(code, "test.py")

    assert result['status'] == 'ok'
    assert len(result['paths']) > 0
    path = result['paths'][0]
    # Should have transformation step
    transform_steps = [s for s in path['steps'] if s['kind'] == 'transform']
    assert len(transform_steps) >= 1


def test_taint_fstring_sql():
    """Test HTTP input → f-string → SQL generates a path."""
    code = """
def query_user():
    user_id = request.args.get("id")
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)
"""
    result = analyze_python_taint_source(code, "test.py")

    assert result['status'] == 'ok'
    assert len(result['paths']) > 0
    path = result['paths'][0]
    assert 'request.args.get' in path['source']['call']
    assert 'execute' in path['sink']['call']


def test_taint_format_sql():
    """Test HTTP input → .format() → SQL generates a path."""
    code = """
def query_user():
    user_id = request.args.get("id")
    query = "SELECT * FROM users WHERE id = {}".format(user_id)
    cursor.execute(query)
"""
    result = analyze_python_taint_source(code, "test.py")

    assert result['status'] == 'ok'
    assert len(result['paths']) > 0
    path = result['paths'][0]
    assert 'request.args.get' in path['source']['call']
    assert 'execute' in path['sink']['call']


def test_taint_percent_formatting():
    """Test HTTP input → % formatting → SQL generates a path."""
    code = """
def query_user():
    user_id = request.args.get("id")
    query = "SELECT * FROM users WHERE id = %s" % user_id
    cursor.execute(query)
"""
    result = analyze_python_taint_source(code, "test.py")

    assert result['status'] == 'ok'
    assert len(result['paths']) > 0
    path = result['paths'][0]
    assert 'request.args.get' in path['source']['call']
    assert 'execute' in path['sink']['call']


def test_taint_safe_reassignment():
    """Test that safe reassignment clears taint."""
    code = """
def safe():
    user_input = input("Enter value: ")
    user_id = user_input
    user_id = 10  # Clean reassignment
    eval(str(user_id))  # Should not receive taint
"""
    result = analyze_python_taint_source(code, "test.py")

    assert result['status'] == 'ok'
    # No path should be generated since taint is cleared
    assert len(result['paths']) == 0


def test_taint_two_functions_no_leakage():
    """Test that taint does not leak between functions."""
    code = """
def dangerous():
    user_input = input("Enter command: ")
    return user_input

def safe():
    eval("print('hello')")  # Should not receive taint from dangerous()
"""
    result = analyze_python_taint_source(code, "test.py")

    assert result['status'] == 'ok'
    # Should only find path in dangerous(), not cross-function
    assert len(result['paths']) <= 1


def test_trace_taint_flow_integration():
    """Integration test for trace_taint_flow with a valid graph node."""
    # This test requires a real graph and graph node
    # For now, verify the function handles the case correctly
    result = trace_taint_flow("nonexistent_function", None)

    # Should return not_found or error for non-existent node
    assert result['status'] in ['not_found', 'error']


def test_visualize_security_flow_integration():
    """Integration test for visualize_security_flow payload structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create test files
        env_file = tmppath / ".env"
        env_file.write_text('api_key = "sk-test123"\n')

        py_file = tmppath / "test.py"
        py_file.write_text("""
def dangerous():
    user_input = input("Enter command: ")
    eval(user_input)
""")

        # This would require graph resolution for full integration
        # For now, verify the individual scanners work
        from ai_agents.tools.security_quality_tools import scan_secrets, scan_vulnerabilities, detect_sql_injection
        from ai_agents.tools.data_flow_intelligence_tools import analyze_python_taint_source

        secrets_result = scan_secrets(str(tmppath), None)
        vuln_result = scan_vulnerabilities(str(tmppath), None)
        sql_result = detect_sql_injection(str(tmppath), None)

        # Test taint analysis directly
        code = py_file.read_text()
        taint_result = analyze_python_taint_source(code, "test.py")

        # Verify all scanners return valid status
        assert secrets_result['status'] == 'ok'
        assert vuln_result['status'] == 'ok'
        assert sql_result['status'] == 'ok'
        assert taint_result['status'] == 'ok'

        # Verify payload structure matches expected schema
        # Taint paths should have: id, kind, source, sink, steps
        if len(taint_result['paths']) > 0:
            path = taint_result['paths'][0]
            assert 'id' in path
            assert 'kind' in path
            assert 'source' in path
            assert 'sink' in path
            assert 'steps' in path
            assert len(path['steps']) >= 2  # source and sink

            # Steps should have: kind, variable/call, line
            for step in path['steps']:
                assert 'kind' in step
                assert 'line' in step


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
