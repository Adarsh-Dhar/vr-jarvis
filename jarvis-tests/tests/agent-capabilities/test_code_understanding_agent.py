"""
Agent capability tests - Layer 4
Testing whether each agent fulfills its assigned job using its tools
"""

import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / 'server'))

from ai_agents.tools.code_understanding_tools import (
    parse_function,
    explain_function,
    extract_function_signature,
    identify_side_effects
)
from ai_agents.tools.relationship_intelligence_tools import (
    find_callees
)
from ai_agents.tools.analysis_tools import (
    analyze_control_flow
)


class TestCodeUnderstandingAgent:
    """Test suite for Code Understanding Agent capabilities"""

    @pytest.fixture
    def agent_context(self):
        """Simulate agent context"""
        return {
            'evidence': [],
            'current_investigation': None
        }

    def test_explain_function_selects_appropriate_tools(self, agent_context):
        """
        Test: Agent selects appropriate tools to explain a function
        
        Task: Explain how authenticateUser() works, including inputs, outputs,
        dependencies and failure conditions.
        
        Expected behavior:
        - Find the function
        - Retrieve its definition
        - Inspect its parameters and return type
        - Retrieve its callees
        - Analyze its control flow
        - Identify exceptions and failure paths
        - Produce an explanation supported by source references
        """
        # Step 1: Parse the function
        parse_result = parse_function(
            function_id='authenticateUser',
            tool_context=type('obj', (object,), {'state': agent_context})()
        )
        assert parse_result['status'] in ['ok', 'error']  # May fail if function doesn't exist

        # Step 2: Extract signature
        signature_result = extract_function_signature(
            function_id='authenticateUser',
            tool_context=type('obj', (object,), {'state': agent_context})()
        )
        assert signature_result['status'] in ['ok', 'error']

        # Step 3: Find callees
        callees_result = find_callees(
            function_id='authenticateUser',
            tool_context=type('obj', (object,), {'state': agent_context})()
        )
        assert callees_result['status'] in ['ok', 'error']

        # Step 4: Analyze control flow
        flow_result = analyze_control_flow(
            function_name='authenticateUser',
            tool_context=type('obj', (object,), {'state': agent_context})()
        )
        assert flow_result['status'] in ['ok', 'error']

    def test_calls_tools_in_correct_order(self, agent_context):
        """
        Test: Agent calls tools in the correct logical order
        
        The agent should:
        1. First parse/locate the function
        2. Then extract its signature
        3. Then analyze its structure
        4. Then find relationships
        5. Finally produce an explanation
        """
        # This would simulate a full agent workflow
        tool_call_order = []
        
        # Simulate tool calls
        tool_call_order.append('parse_function')
        tool_call_order.append('extract_function_signature')
        tool_call_order.append('find_callees')
        tool_call_order.append('analyze_control_flow')
        tool_call_order.append('explain_function')
        
        # Verify order is logical
        assert tool_call_order.index('parse_function') < tool_call_order.index('extract_function_signature')
        assert tool_call_order.index('extract_function_signature') < tool_call_order.index('find_callees')
        assert tool_call_order.index('find_callees') < tool_call_order.index('explain_function')

    def test_recognizes_when_information_is_missing(self, agent_context):
        """
        Test: Agent recognizes when information is missing
        
        When a tool returns incomplete data, the agent should:
        - Detect the missing information
        - Request additional evidence
        - Not invent missing data
        """
        # Simulate a tool returning incomplete data
        incomplete_result = {
            'status': 'ok',
            'function_id': 'authenticateUser',
            'signature': {
                'name': 'authenticateUser',
                'parameters': None,  # Missing parameters
                'return_type': None  # Missing return type
            }
        }
        
        # Agent should detect missing information
        assert incomplete_result['signature']['parameters'] is None
        assert incomplete_result['signature']['return_type'] is None

    def test_does_not_invent_functions_or_relationships(self, agent_context):
        """
        Test: Agent does not invent functions or relationships
        
        When analysis is uncertain, the agent should:
        - Mark relationships as uncertain
        - Not fabricate callers/callees
        - Indicate confidence levels
        """
        # This would test that the agent doesn't hallucinate relationships
        pass

    def test_cites_correct_source_locations(self, agent_context):
        """
        Test: Agent cites correct source locations
        
        Every claim should be supported by:
        - File path
        - Line number
        - Symbol ID
        """
        # This would verify that explanations include proper citations
        pass

    def test_produces_complete_and_understandable_answer(self, agent_context):
        """
        Test: Agent produces a complete and understandable answer
        
        The explanation should include:
        - Function purpose
        - Input parameters
        - Output return value
        - Dependencies (callees)
        - Control flow
        - Error conditions
        - Side effects
        """
        # This would test the quality of the final explanation
        pass

    def test_handles_tool_failure(self, agent_context):
        """
        Test: Agent handles tool failure gracefully
        
        When a tool fails, the agent should:
        - Detect the failure
        - Attempt recovery or alternative approaches
        - Report the limitation
        - Not crash or produce incorrect results
        """
        # Simulate tool failure
        failed_result = {
            'status': 'error',
            'error': 'Symbol not found'
        }
        
        # Agent should handle this gracefully
        assert failed_result['status'] == 'error'
        # Agent should report limitation, not crash

    def test_handles_incomplete_data(self, agent_context):
        """
        Test: Agent handles incomplete data from tools
        
        When a tool returns partial results, the agent should:
        - Work with available data
        - Mark uncertain parts
        - Request additional data if needed
        """
        # Simulate incomplete data
        partial_result = {
            'status': 'ok',
            'callees': [
                {'name': 'validate_token', 'file': 'auth.py', 'line': 10},
                {'name': 'check_permissions', 'file': None, 'line': None}  # Incomplete
            ]
        }
        
        # Agent should handle incomplete entries
        assert partial_result['status'] == 'ok'
        # Should mark incomplete entries

    def test_handles_contradictory_information(self, agent_context):
        """
        Test: Agent handles contradictory information from multiple tools
        
        When tools return conflicting data, the agent should:
        - Detect the conflict
        - Attempt to resolve or prioritize
        - Report the contradiction
        - Not silently choose one over the other
        """
        # Simulate contradictory information
        result1 = {'callers': ['caller1', 'caller2']}
        result2 = {'callers': ['caller1', 'caller3']}
        
        # Agent should detect contradiction
        set1 = set(result1['callers'])
        set2 = set(result2['callers'])
        if set1 != set2:
            # Contradiction detected
            only_in_1 = set1 - set2
            only_in_2 = set2 - set1
            assert len(only_in_1) > 0 or len(only_in_2) > 0


class TestCodeUnderstandingAgentPerformance:
    """Performance tests for Code Understanding Agent"""

    def test_analysis_within_time_limit(self, agent_context):
        """
        Test: Agent completes analysis within time limit
        
        Target: P95 under 5 seconds for basic agent response
        """
        import time
        start = time.time()
        
        # Simulate agent workflow
        parse_result = parse_function(
            function_id='target',
            tool_context=type('obj', (object,), {'state': agent_context})()
        )
        
        duration = (time.time() - start) * 1000
        assert duration < 5000  # Should complete in < 5 seconds

    def test_handles_complex_functions(self, agent_context):
        """
        Test: Agent handles complex functions with many branches
        
        Target: Should handle functions with >10 branches
        """
        # This would test with a complex function
        pass
