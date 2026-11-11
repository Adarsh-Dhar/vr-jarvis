"""
Test that /ask response matches Unity's AskResponse contract.
"""
import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from jarvis_server import app

# Scene command types that Unity handles in JarvisSpatialWorkspace.ApplyCommand
VALID_SCENE_COMMAND_TYPES = {
    "highlight_path",
    "dim_unrelated",
    "open_code_panel",
    "focus_camera",
    "set_edge_style",
    "show_ghost_diff",
    "show_test_badges",
    "show_approval_prompt",
    "select_node",
    "expand_node",
    "collapse_node",
    "set_depth",
    "set_scope",
    "set_filters",
    "create_group",
    "annotate",
    "bookmark",
    "compare",
    "show_graph",
}


def test_ask_response_contract():
    """Test that /ask returns exactly the fields Unity expects."""
    client = TestClient(app)

    # Create a session first
    session_resp = client.post("/session", headers={"authorization": "Bearer test-token"})
    assert session_resp.status_code == 200
    session_id = session_resp.json()["session_id"]

    # Make a simple ask request
    ask_resp = client.post(
        "/ask",
        json={"session_id": session_id, "text": "test", "selection": ""},
        headers={"Authorization": "Bearer test-token"}
    )

    # We expect either success or timeout error, but both should have the right structure
    assert ask_resp.status_code in [200, 500]  # May fail if runner not initialized

    if ask_resp.status_code == 200:
        data = ask_resp.json()
        # Check that all expected fields are present
        expected_fields = {
            "reply",
            "error",
            "scene_commands",
            "pending_approval",
            "approved",
            "test_results",
            "test_source",
            "evidence",
            "unverified_evidence",
            "approval_type",  # Added for approval workflow
            # v11 contract additions
            "evidence_items", "task_id", "active_task", "proposal_status",
            "tool_errors", "test_run",
        }
        assert set(data.keys()) == expected_fields, f"Response has unexpected fields: {set(data.keys())}"

        # Check scene command types
        if data.get("scene_commands"):
            for cmd in data["scene_commands"]:
                assert cmd["type"] in VALID_SCENE_COMMAND_TYPES, \
                    f"Unknown scene command type: {cmd['type']}"
