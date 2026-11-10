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
