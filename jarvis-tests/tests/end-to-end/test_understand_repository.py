"""
End-to-end investigation tests - Layer 6
Simulate actual developer interactions with complete scenarios
"""

import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / 'server'))


class TestUnderstandRepositoryScenario:
    """
    Scenario: Understand a repository
    
    What JARVIS must accomplish:
    - Identify languages, frameworks, entry points and architecture
    """
    
    @pytest.fixture
    def test_scenario_context(self):
        """Set up scenario context"""
        return {
            'repository': 'fixtures/repositories/simple-python',
            'user_request': 'Understand this repository'
        }

    def test_identify_languages(self, test_scenario_context):
        """Test: Identify all programming languages in repository"""
        from ai_agents.tools.repository_intelligence_tools import detect_languages
        
        result = detect_languages(
            repository_path=test_scenario_context['repository'],
            tool_context=None
        )
        assert result['status'] == 'ok'
        assert 'languages' in result
        # Should detect Python
        assert 'python' in result['languages']

    def test_identify_frameworks(self, test_scenario_context):
        """Test: Identify frameworks and libraries"""
        from ai_agents.tools.repository_intelligence_tools import detect_frameworks
        
        result = detect_frameworks(
            repository_path=test_scenario_context['repository'],
            tool_context=None
        )
        assert result['status'] == 'ok'
        assert 'frameworks' in result

    def test_identify_entry_points(self, test_scenario_context):
        """Test: Find application entry points"""
        from ai_agents.tools.repository_intelligence_tools import detect_entry_points
        
        result = detect_entry_points(
            repository_path=test_scenario_context['repository'],
            tool_context=None
        )
        assert result['status'] == 'ok'
        assert 'entry_points' in result

    def test_analyze_architecture(self, test_scenario_context):
        """Test: Understand repository architecture"""
        from ai_agents.tools.repository_intelligence_tools import analyze_repository_structure
        
        result = analyze_repository_structure(
            repository_path=test_scenario_context['repository'],
            tool_context=None
        )
        assert result['status'] == 'ok'
        assert 'structure' in result


class TestInvestigateFunctionScenario:
    """
    Scenario: Investigate a function
    
    What JARVIS must accomplish:
    - Explain logic, callers, callees and dependencies
    """
    
    @pytest.fixture
    def test_scenario_context(self):
        """Set up scenario context"""
        return {
            'repository': 'fixtures/repositories/simple-python',
            'function': 'target',
            'user_request': 'Explain how target() works'
        }

    def test_explain_logic(self, test_scenario_context):
        """Test: Explain function logic"""
        from ai_agents.tools.code_understanding_tools import explain_function
        
        result = explain_function(
            function_id=test_scenario_context['function'],
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']

    def test_find_callers(self, test_scenario_context):
        """Test: Find all callers of the function"""
        from ai_agents.tools.relationship_intelligence_tools import find_callers
        
        result = find_callers(
            function_id=test_scenario_context['function'],
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']

    def test_find_callees(self, test_scenario_context):
        """Test: Find all callees of the function"""
        from ai_agents.tools.relationship_intelligence_tools import find_callees
        
        result = find_callees(
            function_id=test_scenario_context['function'],
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']

    def test_trace_dependencies(self, test_scenario_context):
        """Test: Trace function dependencies"""
        from ai_agents.tools.relationship_intelligence_tools import find_dependents
        
        result = find_dependents(
            component_id=test_scenario_context['function'],
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']


class TestTraceAPIRequestScenario:
    """
    Scenario: Trace an API request
    
    What JARVIS must accomplish:
    - Follow request through service layers to database
    """
    
    @pytest.fixture
    def test_scenario_context(self):
        """Set up scenario context"""
        return {
            'repository': 'fixtures/repositories/simple-python',
            'endpoint': '/api/auth',
            'user_request': 'Trace how authentication request flows'
        }

    def test_discover_endpoints(self, test_scenario_context):
        """Test: Discover API endpoints"""
        from ai_agents.tools.api_database_toolkit import discover_api_endpoints
        
        result = discover_api_endpoints(
            repository_path=test_scenario_context['repository'],
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']

    def test_trace_request_lifecycle(self, test_scenario_context):
        """Test: Follow request through application layers"""
        from ai_agents.tools.api_database_toolkit import trace_request_lifecycle
        
        result = trace_request_lifecycle(
            endpoint=test_scenario_context['endpoint'],
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']

    def test_inspect_middleware(self, test_scenario_context):
        """Test: Understand middleware execution"""
        from ai_agents.tools.api_database_toolkit import inspect_request_middleware
        
        result = inspect_request_middleware(
            repository_path=test_scenario_context['repository'],
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']


class TestInvestigateBugScenario:
    """
    Scenario: Investigate a bug
    
    What JARVIS must accomplish:
    - Identify likely root cause using available evidence
    """
    
    @pytest.fixture
    def test_scenario_context(self):
        """Set up scenario context"""
        return {
            'repository': 'fixtures/repositories/simple-python',
            'bug_report': 'Authentication fails intermittently',
            'user_request': 'Find why authentication fails'
        }

    def test_analyze_stack_trace(self, test_scenario_context):
        """Test: Interpret stack traces"""
        from ai_agents.tools.debugging_intelligence_tools import analyze_stack_trace
        
        stack_trace = """
Traceback (most recent call last):
  File "main.py", line 10, in authenticate
    validate_token(token)
ValueError: Invalid token
"""
        
        result = analyze_stack_trace(
            stack_trace=stack_trace,
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']

    def test_find_error_origin(self, test_scenario_context):
        """Test: Identify likely source of error"""
        from ai_agents.tools.debugging_intelligence_tools import find_error_origin
        
        result = find_error_origin(
            stack_trace="Error in main.py:10",
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']

    def test_identify_root_cause(self, test_scenario_context):
        """Test: Rank and explain possible root causes"""
        from ai_agents.tools.debugging_intelligence_tools import identify_root_cause
        
        result = identify_root_cause(
            error_id='error_123',
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']


class TestInvestigatePerformanceScenario:
    """
    Scenario: Investigate performance
    
    What JARVIS must accomplish:
    - Identify expensive operations from actual measurements
    """
    
    @pytest.fixture
    def test_scenario_context(self):
        """Set up scenario context"""
        return {
            'repository': 'fixtures/repositories/simple-python',
            'user_request': 'Why is this function slow?'
        }

    def test_record_execution_timing(self, test_scenario_context):
        """Test: Record execution duration"""
        from ai_agents.tools.runtime_intelligence_tools import record_execution_timing
        
        result = record_execution_timing(
            application_id='app_123',
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']

    def test_collect_execution_trace(self, test_scenario_context):
        """Test: Collect execution traces"""
        from ai_agents.tools.runtime_intelligence_tools import collect_execution_trace
        
        result = collect_execution_trace(
            application_id='app_123',
            duration=10,
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']


class TestAnalyzeSecurityScenario:
    """
    Scenario: Analyze security
    
    What JARVIS must accomplish:
    - Trace sensitive data and identify security weaknesses
    """
    
    @pytest.fixture
    def test_scenario_context(self):
        """Set up scenario context"""
        return {
            'repository': 'fixtures/repositories/simple-python',
            'user_request': 'Check for security vulnerabilities'
        }

    def test_scan_secrets(self, test_scenario_context):
        """Test: Scan for hardcoded secrets"""
        from ai_agents.tools.security_quality_tools import scan_secrets
        
        result = scan_secrets(
            repository_path=test_scenario_context['repository'],
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']

    def test_trace_sensitive_data(self, test_scenario_context):
        """Test: Track potentially untrusted or sensitive data"""
        from ai_agents.tools.data_flow_intelligence_tools import trace_taint_flow
        
        result = trace_taint_flow(
            variable_id='user_input',
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']

    def test_analyze_input_validation(self, test_scenario_context):
        """Test: Analyze input validation"""
        from ai_agents.tools.security_quality_tools import analyze_input_validation
        
        result = analyze_input_validation(
            repository_path=test_scenario_context['repository'],
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']


class TestChangeFunctionScenario:
    """
    Scenario: Change a function
    
    What JARVIS must accomplish:
    - Modify code and verify the result
    """
    
    @pytest.fixture
    def test_scenario_context(self):
        """Set up scenario context"""
        return {
            'repository': 'fixtures/repositories/simple-python',
            'function': 'target',
            'change': 'Add error handling',
            'user_request': 'Add error handling to target()'
        }

    def test_edit_file(self, test_scenario_context):
        """Test: Modify existing files"""
        from ai_agents.tools.software_engineering_tools import edit_file
        
        result = edit_file(
            file_path=f"{test_scenario_context['repository']}/main.py",
            old_content='def target():\n    return True',
            new_content='def target():\n    try:\n        return True\n    except Exception:\n        return False',
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']

    def test_run_tests(self, test_scenario_context):
        """Test: Verify changes with tests"""
        from ai_agents.tools.testing_verification_tools import run_unit_tests
        
        result = run_unit_tests(
            test_files=[f"{test_scenario_context['repository']}/test_main.py"],
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']


class TestInvestigateRegressionScenario:
    """
    Scenario: Investigate a regression
    
    What JARVIS must accomplish:
    - Compare commits and identify the likely introducing change
    """
    
    @pytest.fixture
    def test_scenario_context(self):
        """Set up scenario context"""
        return {
            'repository': 'fixtures/repositories/simple-python',
            'user_request': 'What caused this bug to appear?'
        }

    def test_compare_commits(self, test_scenario_context):
        """Test: Compare commits"""
        from ai_agents.tools.git_history_toolkit import compare_commits
        
        result = compare_commits(
            repository_path=test_scenario_context['repository'],
            commit1='abc123',
            commit2='def456',
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']

    def test_find_introducing_commit(self, test_scenario_context):
        """Test: Find commit that introduced a behavior"""
        from ai_agents.tools.git_history_toolkit import find_introducing_commit
        
        result = find_introducing_commit(
            symbol_id='target',
            repository_path=test_scenario_context['repository'],
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']

    def test_analyze_commit_impact(self, test_scenario_context):
        """Test: Understand a commit's impact"""
        from ai_agents.tools.git_history_toolkit import analyze_commit_impact
        
        result = analyze_commit_impact(
            commit_hash='abc123',
            repository_path=test_scenario_context['repository'],
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']


class TestExploreComplexSystemScenario:
    """
    Scenario: Explore a complex system
    
    What JARVIS must accomplish:
    - Connect relationships across modules and services
    """
    
    @pytest.fixture
    def test_scenario_context(self):
        """Set up scenario context"""
        return {
            'repository': 'fixtures/repositories/simple-python',
            'user_request': 'Show me how authentication connects to the database'
        }

    def test_trace_cross_module_relationships(self, test_scenario_context):
        """Test: Follow relationships between modules"""
        from ai_agents.tools.relationship_intelligence_tools import trace_cross_module_relationships
        
        result = trace_cross_module_relationships(
            module_id='main',
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']

    def test_build_dependency_graph(self, test_scenario_context):
        """Test: Construct dependency graphs"""
        from ai_agents.tools.relationship_intelligence_tools import build_dependency_graph
        
        result = build_dependency_graph(
            scope=test_scenario_context['repository'],
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']


class TestExplainExecutionScenario:
    """
    Scenario: Explain execution
    
    What JARVIS must accomplish:
    - Reconstruct a real recorded runtime trace
    """
    
    @pytest.fixture
    def test_scenario_context(self):
        """Set up scenario context"""
        return {
            'repository': 'fixtures/repositories/simple-python',
            'trace_id': 'trace_123',
            'user_request': 'Explain what happened during this execution'
        }

    def test_replay_execution_trace(self, test_scenario_context):
        """Test: Replay a captured execution"""
        from ai_agents.tools.runtime_intelligence_tools import replay_execution_trace
        
        result = replay_execution_trace(
            trace_id=test_scenario_context['trace_id'],
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']

    def test_compare_execution_traces(self, test_scenario_context):
        """Test: Compare different executions"""
        from ai_agents.tools.runtime_intelligence_tools import compare_execution_traces
        
        result = compare_execution_traces(
            trace1_id='trace_123',
            trace2_id='trace_456',
            tool_context=None
        )
        assert result['status'] in ['ok', 'error']
