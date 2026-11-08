"""
Runtime Tracing Tests
Comprehensive tests for Python runtime execution tracing.
"""

import pytest
import json
import tempfile
import time
from pathlib import Path
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_agents.runtime_trace_runner import RuntimeTracer
from ai_agents.runtime_trace_store import RuntimeTraceStore, get_trace_store
from ai_agents.tools import runtime_intelligence_tools


class MockToolContext:
    """Mock tool context for testing."""
    def __init__(self, session_id='test_session'):
        self.state = {
            'worktree': Path(__file__).parent.parent.parent / 'jarvis-tests' / 'fixtures' / 'integration-test-infrastructure' / 'runtime',
            'session_id': session_id,
            'scene_commands': [],
        }
        self.agent_name = 'test_agent'


def test_runtime_tracer_basic():
    """Test basic runtime tracer functionality with real fixture."""
    worktree = Path(__file__).parent.parent.parent / 'jarvis-tests' / 'fixtures' / 'integration-test-infrastructure' / 'runtime'
    fixture_path = worktree / 'sample_app.py'

    tracer = RuntimeTracer(worktree=worktree, max_events=100, max_duration=5)

    tracer.start()

    # Execute the fixture application
    import runpy
    try:
        old_cwd = Path.cwd()
        old_sys_path = sys.path.copy()
        old_sys_argv = sys.argv.copy()

        try:
            if str(worktree) not in sys.path:
                sys.path.insert(0, str(worktree))
            import os
            os.chdir(worktree)
            sys.argv = [str(fixture_path)]
            runpy.run_path(str(fixture_path), run_name="__main__")
        finally:
            os.chdir(old_cwd)
            sys.path = old_sys_path
            sys.argv = old_sys_argv
    except Exception as e:
        pytest.fail(f"Fixture execution failed: {e}")

    tracer.stop()

    trace = tracer.get_trace('test_app', 0)

    assert trace['schema_version'] == 1
    assert trace['language'] == 'python'
    assert trace['provenance'] == 'runtime_observed'
    assert trace['status'] in ['completed', 'partial']
    assert isinstance(trace['events'], list)
    assert trace['statistics']['total_events'] >= 0

    # Verify real functions from fixture appear in trace
    call_events = [e for e in trace['events'] if e['event_type'] == 'function_call']
    assert len(call_events) > 0, "Expected to capture function calls from fixture"


def test_runtime_tracer_exception_handling():
    """Test exception event capture with real fixture and exact count."""
    worktree = Path(__file__).parent.parent.parent / 'jarvis-tests' / 'fixtures' / 'integration-test-infrastructure' / 'runtime'
    fixture_path = worktree / 'test_exception_fixture.py'

    tracer = RuntimeTracer(worktree=worktree, max_events=100, max_duration=5)

    tracer.start()

    # Execute the exception fixture
    import runpy
    try:
        old_cwd = Path.cwd()
        old_sys_path = sys.path.copy()
        old_sys_argv = sys.argv.copy()

        try:
            if str(worktree) not in sys.path:
                sys.path.insert(0, str(worktree))
            import os
            os.chdir(worktree)
            sys.argv = [str(fixture_path)]
            runpy.run_path(str(fixture_path), run_name="__main__")
        finally:
            os.chdir(old_cwd)
            sys.path = old_sys_path
            sys.argv = old_sys_argv
    except Exception as e:
        pytest.fail(f"Fixture execution failed: {e}")

    tracer.stop()

    trace = tracer.get_trace('test_app', 0)

    assert trace['schema_version'] == 1
    assert isinstance(trace['events'], list)

    # Verify exceptions were captured - fixture should have exactly 3 unique exceptions
    # 2 from same-line test + 1 from propagation
    exception_events = [e for e in trace['events'] if e['event_type'] == 'exception']
    assert len(exception_events) == 3, f"Expected exactly 3 exception events, got {len(exception_events)}"

    # Verify all exception IDs are distinct
    exception_ids = [e.get('exception_id') for e in exception_events]
    assert len(exception_ids) == len(set(exception_ids)), "All exception IDs should be distinct"

    # Verify exception events have required fields
    for exc in exception_events:
        assert 'exception_type' in exc
        assert 'file' in exc
        assert 'line' in exc
        assert 'function_name' in exc
        assert 'timestamp_ns' in exc


def test_runtime_tracer_recursive_function():
    """Test recursive function with unique invocation IDs using real fixture."""
    worktree = Path(__file__).parent.parent.parent / 'jarvis-tests' / 'fixtures' / 'integration-test-infrastructure' / 'runtime'
    fixture_path = worktree / 'test_recursion_fixture.py'

    tracer = RuntimeTracer(worktree=worktree, max_events=100, max_duration=5)

    tracer.start()

    # Execute the recursion fixture
    import runpy
    try:
        old_cwd = Path.cwd()
        old_sys_path = sys.path.copy()
        old_sys_argv = sys.argv.copy()

        try:
            if str(worktree) not in sys.path:
                sys.path.insert(0, str(worktree))
            import os
            os.chdir(worktree)
            sys.argv = [str(fixture_path)]
            runpy.run_path(str(fixture_path), run_name="__main__")
        finally:
            os.chdir(old_cwd)
            sys.path = old_sys_path
            sys.argv = old_sys_argv
    except Exception as e:
        pytest.fail(f"Fixture execution failed: {e}")

    tracer.stop()

    trace = tracer.get_trace('test_app', 0)

    assert trace['schema_version'] == 1
    assert isinstance(trace['events'], list)

    # Verify recursive calls have distinct IDs
    call_events = [e for e in trace['events'] if e['event_type'] == 'function_call']
    fibonacci_calls = [e for e in call_events if e['function_name'] == 'fibonacci']

    assert len(fibonacci_calls) > 0, "Expected to capture fibonacci calls"

    # Check that all call IDs are unique
    call_ids = [e['call_id'] for e in fibonacci_calls]
    assert len(call_ids) == len(set(call_ids)), "All recursive invocations should have distinct call IDs"

    # Check parent-child relationships
    for call in fibonacci_calls:
        if call['parent_call_id']:
            # Parent should exist in call events
            parent_exists = any(e['call_id'] == call['parent_call_id'] for e in call_events)
            assert parent_exists, f"Parent call ID {call['parent_call_id']} not found in events"


def test_runtime_tracer_event_limit():
    """Test trace truncation at event limit using real fixture."""
    worktree = Path(__file__).parent.parent.parent / 'jarvis-tests' / 'fixtures' / 'integration-test-infrastructure' / 'runtime'
    fixture_path = worktree / 'test_limits_fixture.py'

    tracer = RuntimeTracer(worktree=worktree, max_events=10, max_duration=5)

    tracer.start()

    # Execute the limits fixture with event limit test
    import runpy
    try:
        old_cwd = Path.cwd()
        old_sys_path = sys.path.copy()
        old_sys_argv = sys.argv.copy()

        try:
            if str(worktree) not in sys.path:
                sys.path.insert(0, str(worktree))
            import os
            os.chdir(worktree)
            sys.argv = [str(fixture_path), '--event-limit', '20']
            runpy.run_path(str(fixture_path), run_name="__main__")
        finally:
            os.chdir(old_cwd)
            sys.path = old_sys_path
            sys.argv = old_sys_argv
    except Exception as e:
        pytest.fail(f"Fixture execution failed: {e}")

    tracer.stop()

    trace = tracer.get_trace('test_app', 0)

    assert trace['schema_version'] == 1
    assert isinstance(trace['events'], list)

    # Verify truncation occurred
    assert trace['truncated'] == True, "Trace should be marked as truncated"
    assert len(trace['events']) <= 10, "Should not exceed max_events"

    # Verify event limit specifically caused truncation
    limitations = trace.get('limitations', [])
    assert any('truncated at 10 events' in limit for limit in limitations), "Limitations should mention event limit truncation"


def test_runtime_tracer_duration_limit():
    """Test duration limit enforcement through actual process manager."""
    tool_context = MockToolContext()

    fixture_path = tool_context.state['worktree'] / 'test_limits_fixture.py'

    # Start application with short timeout
    start_result = runtime_intelligence_tools.start_application(
        application_id='test_duration_app',
        environment='dev',
        tool_context=tool_context,
        entrypoint=str(fixture_path),
        arguments=['--duration-limit', '2'],  # Fixture will sleep for 2 seconds
        timeout_seconds=1  # Set timeout to 1 second
    )

    assert start_result['status'] == 'ok', f"Application failed to start: {start_result.get('reason', 'unknown')}"

    # Collect trace - should hit timeout
    collect_result = runtime_intelligence_tools.collect_execution_trace(
        application_id='test_duration_app',
        duration=5,  # Wait longer than timeout
        tool_context=tool_context
    )

    # Must be partial due to timeout (not error)
    assert collect_result['status'] == 'partial', f"Expected partial status, got {collect_result['status']}"
    assert collect_result.get('timeout_hit', False) == True, "Should have hit timeout"
    assert collect_result.get('interrupted', False) == True, "Should have been interrupted"
    assert collect_result['trace_available'] == True, "Trace should be available"

    # Verify partial trace was preserved and has correct timeout reason
    from ai_agents.runtime_trace_store import get_trace_store
    trace_store = get_trace_store()
    trace = trace_store.get_trace(collect_result['trace_id'], tool_context.state.get('session_id', 'default'))
    
    assert trace is not None, "Trace should be available in store"
    assert trace.get('status') == 'partial', "Trace status should be partial"
    
    # Verify correct truncation reason (duration limit, not event limit)
    limitations = trace.get('limitations', [])
    assert any('duration limit' in limit.lower() or 'timeout' in limit.lower() for limit in limitations), \
        f"Should mention duration/timeout limitation, got: {limitations}"


def test_trace_store_basic():
    """Test basic trace store operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = RuntimeTraceStore(storage_dir=Path(tmpdir))

        trace_data = {
            'schema_version': 1,
            'trace_id': 'test_trace_001',
            'application_id': 'test_app',
            'language': 'python',
            'provenance': 'runtime_observed',
            'status': 'completed',
            'events': [],
            'truncated': False,
            'limitations': []
        }

        # Save trace
        result = store.save_trace('test_trace_001', 'session_1', trace_data)
        assert result == True

        # Retrieve trace
        retrieved = store.get_trace('test_trace_001', 'session_1')
        assert retrieved is not None
        assert retrieved['trace_id'] == 'test_trace_001'

        # Session isolation test
        retrieved_wrong_session = store.get_trace('test_trace_001', 'session_2')
        assert retrieved_wrong_session is None

        # Delete trace
        result = store.delete_trace('test_trace_001', 'session_1')
        assert result == True

        # Verify deletion
        retrieved_after_delete = store.get_trace('test_trace_001', 'session_1')
        assert retrieved_after_delete is None


def test_trace_store_session_isolation():
    """Test that traces are isolated between sessions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = RuntimeTraceStore(storage_dir=Path(tmpdir))

        trace_data_1 = {
            'schema_version': 1,
            'trace_id': 'trace_001',
            'application_id': 'app_1',
            'language': 'python',
            'provenance': 'runtime_observed',
            'status': 'completed',
            'events': [],
            'truncated': False,
            'limitations': []
        }

        trace_data_2 = {
            'schema_version': 1,
            'trace_id': 'trace_002',
            'application_id': 'app_2',
            'language': 'python',
            'provenance': 'runtime_observed',
            'status': 'completed',
            'events': [],
            'truncated': False,
            'limitations': []
        }

        # Save traces for different sessions
        store.save_trace('trace_001', 'session_A', trace_data_1)
        store.save_trace('trace_002', 'session_B', trace_data_2)

        # Session A should only see its own traces
        session_a_traces = store.get_session_traces('session_A')
        assert 'trace_001' in session_a_traces
        assert 'trace_002' not in session_a_traces

        # Session B should only see its own traces
        session_b_traces = store.get_session_traces('session_B')
        assert 'trace_002' in session_b_traces
        assert 'trace_001' not in session_b_traces


def test_start_application_basic():
    """Test starting a Python application - must successfully start."""
    tool_context = MockToolContext()

    # Use the sample app
    entrypoint = tool_context.state['worktree'] / 'sample_app.py'

    result = runtime_intelligence_tools.start_application(
        application_id='test_app',
        environment='dev',
        tool_context=tool_context,
        entrypoint=str(entrypoint),
        timeout_seconds=10
    )

    # Must successfully start
    assert result['status'] == 'ok', f"Application failed to start: {result.get('reason', 'unknown')}"
    assert 'pid' in result
    assert 'trace_id' in result


def test_start_application_invalid_entrypoint():
    """Test rejection of invalid entrypoint."""
    tool_context = MockToolContext()

    result = runtime_intelligence_tools.start_application(
        application_id='test_app',
        environment='dev',
        tool_context=tool_context,
        entrypoint='/nonexistent/path.py',
        timeout_seconds=10
    )

    assert result['status'] == 'blocked'


def test_start_application_no_worktree():
    """Test rejection when no worktree is available."""
    tool_context = MockToolContext()
    tool_context.state['worktree'] = None

    result = runtime_intelligence_tools.start_application(
        application_id='test_app',
        environment='dev',
        tool_context=tool_context,
        entrypoint='test.py',
        timeout_seconds=10
    )

    assert result['status'] == 'blocked'


def test_collect_execution_trace_basic():
    """Test collecting execution trace - must assert real events were collected."""
    tool_context = MockToolContext()

    entrypoint = tool_context.state['worktree'] / 'sample_app.py'

    # Start application
    start_result = runtime_intelligence_tools.start_application(
        application_id='test_app',
        environment='dev',
        tool_context=tool_context,
        entrypoint=str(entrypoint),
        timeout_seconds=10
    )

    assert start_result['status'] == 'ok', f"Application failed to start: {start_result.get('reason', 'unknown')}"

    # Wait a moment for execution
    time.sleep(2)

    # Collect trace
    collect_result = runtime_intelligence_tools.collect_execution_trace(
        application_id='test_app',
        duration=15,
        tool_context=tool_context
    )

    assert collect_result['status'] in ['ok', 'partial'], f"Trace collection failed: {collect_result.get('reason', 'unknown')}"
    assert 'trace_id' in collect_result
    assert 'function_calls' in collect_result
    # Assert real events were collected
    assert collect_result['function_calls'] > 0, "Expected real function calls in trace"


def test_record_function_calls():
    """Test recording function calls from trace - assert expected function names."""
    tool_context = MockToolContext()

    entrypoint = tool_context.state['worktree'] / 'sample_app.py'

    # Start application
    start_result = runtime_intelligence_tools.start_application(
        application_id='test_app',
        environment='dev',
        tool_context=tool_context,
        entrypoint=str(entrypoint),
        timeout_seconds=10
    )

    if start_result['status'] == 'ok':
        time.sleep(2)

        # Collect trace
        collect_result = runtime_intelligence_tools.collect_execution_trace(
            application_id='test_app',
            duration=15,
            tool_context=tool_context
        )

        if collect_result['status'] in ['ok', 'partial']:
            # Record function calls
            record_result = runtime_intelligence_tools.record_function_calls(
                application_id='test_app',
                tool_context=tool_context
            )

            assert record_result['status'] == 'ok'
            assert 'function_calls' in record_result

            # Assert expected function names appear
            function_names = [call.get('function_name') for call in record_result['function_calls']]
            assert len(function_names) > 0, "Expected function names in trace"
            # Check for some expected functions from sample_app.py
            expected_functions = ['main', 'process', 'calculate_statistics']
            found_expected = any(name in function_names for name in expected_functions)
            assert found_expected, f"Expected to find at least one of {expected_functions} in {function_names}"
    else:
        pytest.fail(f"Application failed to start: {start_result.get('reason', 'unknown')}")


def test_record_execution_timing():
    """Test recording execution timing - assert actual timing values."""
    tool_context = MockToolContext()

    entrypoint = tool_context.state['worktree'] / 'sample_app.py'

    # Start application
    start_result = runtime_intelligence_tools.start_application(
        application_id='test_app',
        environment='dev',
        tool_context=tool_context,
        entrypoint=str(entrypoint),
        timeout_seconds=10
    )

    if start_result['status'] == 'ok':
        time.sleep(2)

        # Collect trace
        collect_result = runtime_intelligence_tools.collect_execution_trace(
            application_id='test_app',
            duration=15,
            tool_context=tool_context
        )

        if collect_result['status'] in ['ok', 'partial']:
            # Record timing
            timing_result = runtime_intelligence_tools.record_execution_timing(
                application_id='test_app',
                tool_context=tool_context
            )

            assert timing_result['status'] == 'ok'
            assert 'timing_data' in timing_result

            # Assert actual timing values are present and non-negative
            for timing in timing_result['timing_data']:
                assert 'duration_ms' in timing
                assert timing['duration_ms'] >= 0, "Duration should be non-negative"
                assert 'elapsed_ms' in timing
    else:
        pytest.fail(f"Application failed to start: {start_result.get('reason', 'unknown')}")


def test_advanced_tools_unsupported():
    """Test that advanced tools return unsupported status."""
    tool_context = MockToolContext()

    advanced_tools = [
        ('attach_debugger', {'application_id': 'test_app', 'tool_context': tool_context}),
        ('record_function_arguments', {'application_id': 'test_app', 'function_id': 'func_1', 'tool_context': tool_context}),
        ('record_function_returns', {'application_id': 'test_app', 'function_id': 'func_1', 'tool_context': tool_context}),
        ('record_variable_state', {'application_id': 'test_app', 'variable_id': 'var_1', 'tool_context': tool_context}),
        ('record_memory_usage', {'application_id': 'test_app', 'tool_context': tool_context}),
        ('record_cpu_usage', {'application_id': 'test_app', 'tool_context': tool_context}),
    ]

    for tool_name, kwargs in advanced_tools:
        tool_func = getattr(runtime_intelligence_tools, tool_name)
        result = tool_func(**kwargs)
        assert result['status'] == 'unsupported', f"{tool_name} should return unsupported"


def test_complete_workflow():
    """Test the complete workflow: start → collect → visualize."""
    from ai_agents.tools import visualization_spatial_tools

    tool_context = MockToolContext()

    entrypoint = tool_context.state['worktree'] / 'sample_app.py'

    # Step 1: Start application
    start_result = runtime_intelligence_tools.start_application(
        application_id='test_app',
        environment='dev',
        tool_context=tool_context,
        entrypoint=str(entrypoint),
        timeout_seconds=10
    )

    assert start_result['status'] == 'ok', f"Could not start application: {start_result.get('reason', 'unknown')}"

    # Step 2: Collect trace
    time.sleep(2)
    collect_result = runtime_intelligence_tools.collect_execution_trace(
        application_id='test_app',
        duration=15,
        tool_context=tool_context
    )

    assert collect_result['status'] in ['ok', 'partial'], f"Could not collect trace: {collect_result.get('reason', 'unknown')}"

    # Step 3: Visualize execution flow
    trace_id = collect_result['trace_id']
    visualize_result = visualization_spatial_tools.visualize_execution_flow(
        trace_id=trace_id,
        tool_context=tool_context
    )

    # Verify scene commands were emitted successfully
    assert visualize_result['status'] == 'ok', f"Visualization failed: {visualize_result.get('error', 'unknown')}"

    # Check that scene commands were added
    scene_commands = tool_context.state.get('scene_commands', [])
    assert len(scene_commands) >= 2  # show_graph and show_runtime_panel

    # Verify command types
    command_types = [cmd['type'] for cmd in scene_commands]
    assert 'show_graph' in command_types
    assert 'show_runtime_panel' in command_types

    # Verify show_graph command has nodes and edges
    show_graph_cmd = next(cmd for cmd in scene_commands if cmd['type'] == 'show_graph')
    assert 'nodes' in show_graph_cmd
    assert 'edges' in show_graph_cmd
    assert len(show_graph_cmd['nodes']) > 0, "Runtime graph should have nodes"
    assert len(show_graph_cmd['edges']) > 0, "Runtime graph should have at least one edge"
    
    # Verify edges represent meaningful parent-child relationships
    # Each edge should have src and dst node IDs that exist in nodes
    node_ids = {node['id'] for node in show_graph_cmd['nodes']}
    for edge in show_graph_cmd['edges']:
        assert 'src' in edge
        assert 'dst' in edge
        assert edge['src'] in node_ids, f"Edge 'src' node {edge['src']} not in nodes"
        assert edge['dst'] in node_ids, f"Edge 'dst' node {edge['dst']} not in nodes"

    # Verify show_runtime_panel command has expected data
    show_panel_cmd = next(cmd for cmd in scene_commands if cmd['type'] == 'show_runtime_panel')
    assert 'trace_id' in show_panel_cmd
    assert 'application_id' in show_panel_cmd
    assert 'runtime_event_count' in show_panel_cmd
    assert 'runtime_events' in show_panel_cmd
    assert 'runtime_limitations' in show_panel_cmd


def test_function_returns_match_calls():
    """Test that every return event matches its original call ID."""
    worktree = Path(__file__).parent.parent.parent / 'jarvis-tests' / 'fixtures' / 'integration-test-infrastructure' / 'runtime'
    fixture_path = worktree / 'sample_app.py'

    tracer = RuntimeTracer(worktree=worktree, max_events=100, max_duration=5)

    tracer.start()

    # Execute the fixture
    import runpy
    try:
        old_cwd = Path.cwd()
        old_sys_path = sys.path.copy()
        old_sys_argv = sys.argv.copy()

        try:
            if str(worktree) not in sys.path:
                sys.path.insert(0, str(worktree))
            import os
            os.chdir(worktree)
            sys.argv = [str(fixture_path)]
            runpy.run_path(str(fixture_path), run_name="__main__")
        finally:
            os.chdir(old_cwd)
            sys.path = old_sys_path
            sys.argv = old_sys_argv
    except Exception as e:
        pytest.fail(f"Fixture execution failed: {e}")

    tracer.stop()

    trace = tracer.get_trace('test_app', 0)

    # Collect call and return events
    call_events = {e['call_id']: e for e in trace['events'] if e['event_type'] == 'function_call'}
    return_events = [e for e in trace['events'] if e['event_type'] == 'function_return']

    # Assert return events exist
    assert len(return_events) > 0, "Expected return events in trace"

    # Verify every return event has a matching call event
    for ret in return_events:
        call_id = ret['call_id']
        assert call_id in call_events, f"Return event has call_id {call_id} with no matching call event"


def test_cli_arguments_forwarding():
    """Test that CLI arguments are forwarded correctly through the actual subprocess runner."""
    tool_context = MockToolContext()

    fixture_path = tool_context.state['worktree'] / 'test_args_fixture.py'

    # Start application with arguments through the real runner
    start_result = runtime_intelligence_tools.start_application(
        application_id='test_args_app',
        environment='dev',
        tool_context=tool_context,
        entrypoint=str(fixture_path),
        arguments=['positional_arg', '--config', 'test.json'],
        timeout_seconds=10
    )

    assert start_result['status'] == 'ok', f"Application failed to start: {start_result.get('reason', 'unknown')}"

    # Wait for execution
    time.sleep(2)

    # Capture application logs to verify exact arguments
    logs_result = runtime_intelligence_tools.capture_application_logs(
        application_id='test_args_app',
        tool_context=tool_context
    )

    assert logs_result['status'] == 'ok', f"Failed to capture logs: {logs_result.get('reason', 'unknown')}"

    # Collect trace
    collect_result = runtime_intelligence_tools.collect_execution_trace(
        application_id='test_args_app',
        duration=15,
        tool_context=tool_context
    )

    assert collect_result['status'] in ['ok', 'partial'], f"Trace collection failed: {collect_result.get('reason', 'unknown')}"
    assert collect_result['trace_available'] == True

    # Load trace and verify exact arguments were received
    from ai_agents.runtime_trace_store import get_trace_store
    trace_store = get_trace_store()
    trace = trace_store.get_trace(collect_result['trace_id'], tool_context.state.get('session_id', 'default'))
    
    assert trace is not None, "Trace should be available"
    
    # The fixture prints received arguments - verify exact arguments in logs
    stdout = logs_result.get('stdout_excerpt', '')
    assert 'positional_arg' in stdout, "Expected positional_arg in stdout"
    assert '--config' in stdout, "Expected --config in stdout"
    assert 'test.json' in stdout, "Expected test.json in stdout"
    
    # Verify the function calls exist
    assert collect_result['function_calls'] > 0, "Expected function calls in trace"


def test_local_imports():
    """Test that imports from sibling files work through the actual subprocess runner."""
    tool_context = MockToolContext()

    fixture_path = tool_context.state['worktree'] / 'test_import_fixture.py'

    # Start application through the real runner
    start_result = runtime_intelligence_tools.start_application(
        application_id='test_import_app',
        environment='dev',
        tool_context=tool_context,
        entrypoint=str(fixture_path),
        timeout_seconds=10
    )

    assert start_result['status'] == 'ok', f"Application failed to start: {start_result.get('reason', 'unknown')}"

    # Wait for execution
    time.sleep(2)

    # Collect trace
    collect_result = runtime_intelligence_tools.collect_execution_trace(
        application_id='test_import_app',
        duration=15,
        tool_context=tool_context
    )

    assert collect_result['status'] in ['ok', 'partial'], f"Trace collection failed: {collect_result.get('reason', 'unknown')}"
    assert collect_result['trace_available'] == True

    # Load trace and verify helper functions appear
    from ai_agents.runtime_trace_store import get_trace_store
    trace_store = get_trace_store()
    trace = trace_store.get_trace(collect_result['trace_id'], tool_context.state.get('session_id', 'default'))
    
    assert trace is not None, "Trace should be available"
    
    # Verify helper_function and another_helper appear in trace
    call_events = [e for e in trace['events'] if e['event_type'] == 'function_call']
    function_names = [e['function_name'] for e in call_events]
    
    assert 'helper_function' in function_names, "Expected helper_function in trace"
    assert 'another_helper' in function_names, "Expected another_helper in trace"


def test_multiple_unsupported_reported():
    """Test that multiple unsupported execution types are all reported."""
    worktree = Path(__file__).parent.parent.parent / 'jarvis-tests' / 'fixtures' / 'integration-test-infrastructure' / 'runtime'
    fixture_path = worktree / 'test_multiple_unsupported_fixture.py'

    tracer = RuntimeTracer(worktree=worktree, max_events=100, max_duration=5)

    tracer.start()

    # Execute the multiple unsupported fixture
    import runpy
    try:
        old_cwd = Path.cwd()
        old_sys_path = sys.path.copy()
        old_sys_argv = sys.argv.copy()

        try:
            if str(worktree) not in sys.path:
                sys.path.insert(0, str(worktree))
            import os
            os.chdir(worktree)
            sys.argv = [str(fixture_path)]
            runpy.run_path(str(fixture_path), run_name="__main__")
        finally:
            os.chdir(old_cwd)
            sys.path = old_sys_path
            sys.argv = old_sys_argv
    except Exception as e:
        pytest.fail(f"Fixture execution failed: {e}")

    tracer.stop()

    trace = tracer.get_trace('test_app', 0)

    # Verify status is partial
    assert trace['status'] == 'partial', "Should be marked as partial due to unsupported features"

    # Verify all distinct limitations are reported
    limitations = trace.get('limitations', [])
    assert len(limitations) >= 2, "Should report multiple unsupported features"

    # Check for expected unsupported types
    limitation_str = ' '.join(limitations).lower()
    assert 'generator' in limitation_str or 'coroutine' in limitation_str, "Should report generator/coroutine"
    assert 'background' in limitation_str or 'thread' in limitation_str, "Should report background thread"


def test_manual_stop_application():
    """Test manually stopping an application and preserving its trace."""
    tool_context = MockToolContext()

    fixture_path = tool_context.state['worktree'] / 'test_long_running_fixture.py'

    # Start long-running application
    start_result = runtime_intelligence_tools.start_application(
        application_id='test_stop_app',
        environment='dev',
        tool_context=tool_context,
        entrypoint=str(fixture_path),
        timeout_seconds=10
    )

    assert start_result['status'] == 'ok', f"Application failed to start: {start_result.get('reason', 'unknown')}"

    # Wait briefly for some execution
    time.sleep(2)

    # Manually stop the application
    stop_result = runtime_intelligence_tools.stop_application(
        application_id='test_stop_app',
        tool_context=tool_context
    )

    assert stop_result['status'] in ['ok', 'partial'], f"Stop failed: {stop_result.get('error', 'unknown')}"

    # Verify trace was saved to trace store
    assert stop_result.get('trace_id') is not None, "Trace ID should be available after manual stop"
    
    from ai_agents.runtime_trace_store import get_trace_store
    trace_store = get_trace_store()
    trace = trace_store.get_trace(stop_result['trace_id'], tool_context.state.get('session_id', 'default'))
    
    assert trace is not None, "Trace should be available in store after manual stop"
    assert trace.get('provenance') == 'runtime_observed', "Trace should have correct provenance"
    assert trace.get('status') == 'partial', "Trace should be partial after manual stop"


def test_watchdog_automatic_timeout():
    """Test that watchdog automatically terminates application after timeout without trace collection."""
    tool_context = MockToolContext()

    fixture_path = tool_context.state['worktree'] / 'test_limits_fixture.py'

    # Start application with very short timeout
    start_result = runtime_intelligence_tools.start_application(
        application_id='test_watchdog_timeout',
        environment='dev',
        tool_context=tool_context,
        entrypoint=str(fixture_path),
        arguments=['--duration-limit', '5'],  # Fixture will sleep for 5 seconds
        timeout_seconds=1  # Watchdog should terminate after 1 second
    )

    assert start_result['status'] == 'ok', f"Application failed to start: {start_result.get('reason', 'unknown')}"

    # Wait for watchdog to terminate the process (timeout + grace period)
    time.sleep(3)

    # Now collect trace - should show timeout termination, not manual interruption
    collect_result = runtime_intelligence_tools.collect_execution_trace(
        application_id='test_watchdog_timeout',
        duration=5,
        tool_context=tool_context
    )

    assert collect_result['status'] == 'partial', f"Expected partial status, got {collect_result['status']}"
    assert collect_result.get('timeout_hit', False) == True, "Should have hit timeout"
    assert collect_result.get('interrupted', False) == True, "Should have been interrupted"
    assert collect_result['trace_available'] == True, "Trace should be available"

    # Verify the trace limitations show duration limit, not SIGTERM/manual interruption
    from ai_agents.runtime_trace_store import get_trace_store
    trace_store = get_trace_store()
    trace = trace_store.get_trace(collect_result['trace_id'], tool_context.state.get('session_id', 'default'))
    
    assert trace is not None, "Trace should be available in store"
    assert trace.get('status') == 'partial', "Trace status should be partial"
    
    limitations = trace.get('limitations', [])
    limitation_str = ' '.join(limitations).lower()
    
    # Should mention duration limit or timeout
    assert 'duration limit' in limitation_str or 'timeout' in limitation_str, \
        f"Should mention duration/timeout limitation, got: {limitations}"
    
    # Should NOT mention SIGTERM or manual interruption (watchdog timeout is automatic)
    assert 'sigterm' not in limitation_str, f"Should not mention SIGTERM for automatic timeout, got: {limitations}"
    assert 'interrupted' not in limitation_str or 'duration limit' in limitation_str, \
        f"Should classify as duration limit, not manual interruption, got: {limitations}"


def test_watchdog_id_reuse_safety():
    """Test that old watchdog cannot terminate newer application with same ID."""
    tool_context = MockToolContext()

    fixture_path = tool_context.state['worktree'] / 'test_limits_fixture.py'

    # Start first application with short timeout
    start_result1 = runtime_intelligence_tools.start_application(
        application_id='test_reuse_app',
        environment='dev',
        tool_context=tool_context,
        entrypoint=str(fixture_path),
        arguments=['--duration-limit', '10'],  # Will sleep for 10 seconds
        timeout_seconds=1  # Watchdog will terminate after 1 second
    )

    assert start_result1['status'] == 'ok', f"First application failed to start: {start_result1.get('reason', 'unknown')}"

    # Wait for first application to be terminated by watchdog
    time.sleep(3)

    # Collect trace for first application to unregister it
    collect_result1 = runtime_intelligence_tools.collect_execution_trace(
        application_id='test_reuse_app',
        duration=5,
        tool_context=tool_context
    )

    assert collect_result1['status'] == 'partial', f"First application should be partial, got {collect_result1['status']}"

    # Start second application with same ID but longer timeout
    start_result2 = runtime_intelligence_tools.start_application(
        application_id='test_reuse_app',
        environment='dev',
        tool_context=tool_context,
        entrypoint=str(fixture_path),
        arguments=['--duration-limit', '3'],  # Will sleep for 3 seconds
        timeout_seconds=10  # Longer timeout
    )

    assert start_result2['status'] == 'ok', f"Second application failed to start: {start_result2.get('reason', 'unknown')}"

    # Wait for second application to complete naturally (3 seconds)
    time.sleep(4)

    # Collect trace for second application
    collect_result2 = runtime_intelligence_tools.collect_execution_trace(
        application_id='test_reuse_app',
        duration=5,
        tool_context=tool_context
    )

    # Second application should complete successfully (not be terminated by old watchdog)
    assert collect_result2['status'] in ['ok', 'partial'], f"Second application collection failed: {collect_result2.get('reason', 'unknown')}"
    assert collect_result2.get('timeout_hit', False) == False, "Second application should not hit timeout from old watchdog"
    
    # Verify second application completed naturally
    from ai_agents.runtime_trace_store import get_trace_store
    trace_store = get_trace_store()
    trace = trace_store.get_trace(collect_result2['trace_id'], tool_context.state.get('session_id', 'default'))
    
    assert trace is not None, "Second application trace should be available"
    assert trace.get('status') == 'completed', f"Second application should complete naturally, got status: {trace.get('status')}"


def test_trace_limitation_classification():
    """Test that trace limitations correctly distinguish timeout from manual interruption for VR panel."""
    tool_context = MockToolContext()

    fixture_path = tool_context.state['worktree'] / 'test_limits_fixture.py'

    # Test 1: Automatic timeout via watchdog
    start_result1 = runtime_intelligence_tools.start_application(
        application_id='test_classify_timeout',
        environment='dev',
        tool_context=tool_context,
        entrypoint=str(fixture_path),
        arguments=['--duration-limit', '5'],
        timeout_seconds=1  # Watchdog will terminate
    )

    assert start_result1['status'] == 'ok'

    # Wait for watchdog to terminate
    time.sleep(3)

    collect_result1 = runtime_intelligence_tools.collect_execution_trace(
        application_id='test_classify_timeout',
        duration=5,
        tool_context=tool_context
    )

    assert collect_result1['status'] == 'partial'
    assert collect_result1.get('timeout_hit', False) == True

    # Verify limitations for VR panel
    from ai_agents.runtime_trace_store import get_trace_store
    trace_store = get_trace_store()
    trace1 = trace_store.get_trace(collect_result1['trace_id'], tool_context.state.get('session_id', 'default'))
    
    limitations1 = trace1.get('limitations', [])
    limitation_str1 = ' '.join(limitations1).lower()
    
    # Automatic timeout should mention duration limit, not SIGTERM
    assert 'duration limit' in limitation_str1 or 'timeout' in limitation_str1, \
        f"Timeout should mention duration limit, got: {limitations1}"
    assert 'sigterm' not in limitation_str1, \
        f"Timeout should not mention SIGTERM, got: {limitations1}"

    # Test 2: Manual interruption
    start_result2 = runtime_intelligence_tools.start_application(
        application_id='test_classify_manual',
        environment='dev',
        tool_context=tool_context,
        entrypoint=str(fixture_path),
        arguments=['--duration-limit', '10'],
        timeout_seconds=30  # Long timeout so watchdog won't fire
    )

    assert start_result2['status'] == 'ok'

    # Wait briefly then manually stop
    time.sleep(2)
    stop_result = runtime_intelligence_tools.stop_application(
        application_id='test_classify_manual',
        tool_context=tool_context
    )

    assert stop_result['status'] in ['ok', 'partial']

    # Verify limitations for VR panel
    if stop_result.get('trace_id'):
        trace2 = trace_store.get_trace(stop_result['trace_id'], tool_context.state.get('session_id', 'default'))
        limitations2 = trace2.get('limitations', [])
        limitation_str2 = ' '.join(limitations2).lower()
        
        # Manual interruption should mention SIGTERM or interrupted
        assert 'sigterm' in limitation_str2 or 'interrupted' in limitation_str2, \
            f"Manual stop should mention SIGTERM/interrupted, got: {limitations2}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
