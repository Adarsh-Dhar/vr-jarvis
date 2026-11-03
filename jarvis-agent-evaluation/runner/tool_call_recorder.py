#!/usr/bin/env python3
"""
Tool Call Recorder
Captures all tool invocations and their details during agent execution
"""

import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime


class ToolCallRecorder:
    """Records all tool calls made by an agent during execution."""

    def __init__(self):
        self.tool_calls = []
        self.start_time = None
        self.end_time = None

    def start_recording(self):
        """Start recording tool calls."""
        self.start_time = time.time()
        self.tool_calls = []

    def stop_recording(self):
        """Stop recording tool calls."""
        self.end_time = time.time()

    def record_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        return_value: Any,
        success: bool,
        duration_ms: float,
        error: Optional[str] = None
    ) -> None:
        """
        Record a single tool call.

        Args:
            tool_name: Name of the tool called
            arguments: Arguments passed to the tool
            return_value: Value returned by the tool
            success: Whether the tool call succeeded
            duration_ms: Duration of the tool call in milliseconds
            error: Error message if the call failed
        """
        call_record = {
            'timestamp': datetime.now().isoformat(),
            'tool_name': tool_name,
            'arguments': arguments,
            'return_value': return_value,
            'success': success,
            'duration_ms': duration_ms,
            'error': error
        }
        self.tool_calls.append(call_record)

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all recorded tool calls."""
        if not self.tool_calls:
            return {
                'total_calls': 0,
                'successful_calls': 0,
                'failed_calls': 0,
                'total_duration_ms': 0,
                'calls_by_tool': {}
            }

        total_calls = len(self.tool_calls)
        successful_calls = sum(1 for call in self.tool_calls if call['success'])
        failed_calls = total_calls - successful_calls
        total_duration_ms = sum(call['duration_ms'] for call in self.tool_calls)

        # Group by tool name
        calls_by_tool = {}
        for call in self.tool_calls:
            tool_name = call['tool_name']
            if tool_name not in calls_by_tool:
                calls_by_tool[tool_name] = {'count': 0, 'successful': 0, 'failed': 0, 'total_duration_ms': 0}
            calls_by_tool[tool_name]['count'] += 1
            if call['success']:
                calls_by_tool[tool_name]['successful'] += 1
            else:
                calls_by_tool[tool_name]['failed'] += 1
            calls_by_tool[tool_name]['total_duration_ms'] += call['duration_ms']

        return {
            'total_calls': total_calls,
            'successful_calls': successful_calls,
            'failed_calls': failed_calls,
            'total_duration_ms': total_duration_ms,
            'average_duration_ms': total_duration_ms / total_calls if total_calls > 0 else 0,
            'calls_by_tool': calls_by_tool
        }

    def get_failed_calls(self) -> List[Dict[str, Any]]:
        """Get all failed tool calls."""
        return [call for call in self.tool_calls if not call['success']]

    def get_calls_by_tool(self, tool_name: str) -> List[Dict[str, Any]]:
        """Get all calls to a specific tool."""
        return [call for call in self.tool_calls if call['tool_name'] == tool_name]

    def to_dict(self) -> Dict[str, Any]:
        """Convert the entire recording to a dictionary."""
        return {
            'start_time': datetime.fromtimestamp(self.start_time).isoformat() if self.start_time else None,
            'end_time': datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None,
            'total_duration_seconds': (self.end_time - self.start_time) if self.start_time and self.end_time else None,
            'tool_calls': self.tool_calls,
            'summary': self.get_summary()
        }

    def save_to_file(self, filepath: str) -> None:
        """Save the recording to a JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


class ToolCallValidator:
    """Validates tool calls against agent specifications."""

    def __init__(self, agent_spec: Dict[str, Any]):
        self.agent_spec = agent_spec
        self.allowed_tools = set(agent_spec.get('allowed_tools', []))

    def validate_tool_call(self, tool_name: str) -> bool:
        """
        Check if a tool call is allowed for this agent.

        Args:
            tool_name: Name of the tool being called

        Returns:
            True if the tool is allowed, False otherwise
        """
        return tool_name in self.allowed_tools

    def validate_all_calls(self, tool_calls: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate all tool calls in a recording.

        Args:
            tool_calls: List of tool call records

        Returns:
            Dictionary with validation results
        """
        unauthorized_calls = []
        for call in tool_calls:
            tool_name = call['tool_name']
            if not self.validate_tool_call(tool_name):
                unauthorized_calls.append({
                    'tool_name': tool_name,
                    'timestamp': call['timestamp'],
                    'arguments': call['arguments']
                })

        return {
            'total_calls': len(tool_calls),
            'authorized_calls': len(tool_calls) - len(unauthorized_calls),
            'unauthorized_calls': len(unauthorized_calls),
            'unauthorized_call_details': unauthorized_calls,
            'all_authorized': len(unauthorized_calls) == 0
        }
