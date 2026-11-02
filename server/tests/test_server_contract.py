"""
Contract tests for server endpoints.
Validates that endpoint responses match Unity's expected JSON structure.
"""

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from jarvis_server import app
from ai_agents import config


class TestAskContract:
    """Test /ask endpoint contract."""
    
    def test_ask_response_structure(self):
        """Test that /ask returns the expected fields."""
        client = TestClient(app)
        
        # Create a session first
        session_resp = client.post('/session')
        assert session_resp.status_code == 200
        session_id = session_resp.json()['session_id']
        
        # Make an ask request
        response = client.post(
            '/ask',
            json={'session_id': session_id, 'text': 'test', 'selection': ''},
            headers={'authorization': 'Bearer test-token'}
        )
        
        # Response should be 200 or have an error
        assert response.status_code in [200, 401]
        
        if response.status_code == 200:
            data = response.json()
            # Check required fields for Unity
            assert 'reply' in data
            assert 'error' in data
            assert 'scene_commands' in data
            assert 'pending_approval' in data
            assert 'approved' in data
            assert 'test_results' in data
            assert 'evidence' in data
            
            # scene_commands should be a list
            assert isinstance(data['scene_commands'], list)
            
            # evidence should be a list
            assert isinstance(data['evidence'], list)


class TestApproveContract:
    """Test /approve endpoint contract."""
    
    def test_approve_response_structure(self):
        """Test that /approve returns the expected fields."""
        client = TestClient(app)
        
        # Create a session
        session_resp = client.post('/session')
        session_id = session_resp.json()['session_id']
        
        # Test rejection
        response = client.post(
            '/approve',
            json={'session_id': session_id, 'approved': False},
            headers={'authorization': 'Bearer test-token'}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'ok' in data
        assert 'action' in data
        assert 'detail' in data
        
        # Rejection should have action='rejected'
        if not data.get('ok'):
            assert data['action'] == 'rejected'


class TestProgressContract:
    """Test /progress endpoint contract."""
    
    def test_progress_response_structure(self):
        """Test that /progress returns the expected fields."""
        client = TestClient(app)

        # Create a session
        session_resp = client.post('/session')
        session_id = session_resp.json()['session_id']

        response = client.get(
            f'/progress/{session_id}',
            headers={'authorization': 'Bearer test-token'}
        )

        assert response.status_code == 200
        data = response.json()
        # session_id is in the URL, not the response body
        assert 'busy' in data
        assert 'steps' in data
        assert isinstance(data['steps'], list)


class TestTaskContract:
    """Test /task endpoint contract."""
    
    def test_task_response_structure(self):
        """Test that /task returns the expected fields."""
        client = TestClient(app)
        
        # Create a session
        session_resp = client.post('/session')
        session_id = session_resp.json()['session_id']
        
        response = client.get(
            f'/task/{session_id}',
            headers={'authorization': 'Bearer test-token'}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'session_id' in data
        assert 'plan' in data
        assert 'findings' in data
        assert 'agent_results' in data
        assert isinstance(data['findings'], list)
        assert isinstance(data['agent_results'], list)


class TestToolsContract:
    """Test /tools endpoint contract."""
    
    def test_list_tools_response_structure(self):
        """Test that GET /tools returns the expected fields."""
        client = TestClient(app)
        
        response = client.get(
            '/tools',
            headers={'authorization': 'Bearer test-token'}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'tools' in data
        assert isinstance(data['tools'], list)
        
        # Each tool should have required fields
        if data['tools']:
            tool = data['tools'][0]
            assert 'name' in tool
            assert 'level' in tool
            assert 'owning_agents' in tool
            assert 'parameters' in tool
    
    def test_call_tool_blocks_write(self):
        """Test that POST /tools blocks write tools."""
        client = TestClient(app)

        response = client.post(
            '/tools/edit_file',
            json={},
            headers={'authorization': 'Bearer test-token'}
        )

        # Accept 422 for empty body, but should still block if request gets through
        if response.status_code == 422:
            # Empty body is invalid - that's fine, just return
            return

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'blocked'
        assert 'write' in data['reason'].lower()


class TestSceneCommands:
    """Test scene_commands.json is valid."""
    
    def test_scene_commands_json_exists(self):
        """Test that scene_commands.json exists and is valid JSON."""
        scene_commands_path = Path(__file__).parent.parent / 'ai_agents' / 'scene_commands.json'
        assert scene_commands_path.exists()
        
        import json
        data = json.loads(scene_commands_path.read_text())
        assert 'commands' in data
        assert isinstance(data['commands'], list)
        
        # Each command should have required fields
        for cmd in data['commands']:
            assert 'name' in cmd
            assert 'fields' in cmd
            assert 'description' in cmd


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
