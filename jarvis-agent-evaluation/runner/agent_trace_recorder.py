#!/usr/bin/env python3
"""
Agent Trace Recorder
Records the complete observable execution trace of an agent including decisions, state changes, and delegation
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime


class AgentTraceRecorder:
    """Records the complete execution trace of an agent."""

    def __init__(self, agent_id: str, agent_version: str, model: str):
        self.agent_id = agent_id
        self.agent_version = agent_version
        self.model = model
        self.trace = []
        self.start_time = None
        self.end_time = None

    def start_recording(self, initial_task: str, initial_context: Dict[str, Any]) -> None:
        """
        Start recording a new execution trace.

        Args:
            initial_task: The initial task given to the agent
            initial_context: The initial context provided to the agent
        """
        self.start_time = datetime.now()
        self.trace = []

        # Record initial state
        self.record_event('execution_start', {
            'task': initial_task,
            'context': initial_context,
            'timestamp': self.start_time.isoformat()
        })

    def stop_recording(self, final_output: Dict[str, Any]) -> None:
        """
        Stop recording and save the final output.

        Args:
            final_output: The final output from the agent
        """
        self.end_time = datetime.now()

        # Record final state
        self.record_event('execution_end', {
            'output': final_output,
            'timestamp': self.end_time.isoformat(),
            'duration_seconds': (self.end_time - self.start_time).total_seconds()
        })

    def record_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Record an event in the trace.

        Args:
            event_type: Type of event (e.g., 'planning', 'tool_call', 'decision')
            data: Event data
        """
        event = {
            'event_type': event_type,
            'timestamp': datetime.now().isoformat(),
            'data': data
        }
        self.trace.append(event)

    def record_planning(self, plan: Dict[str, Any]) -> None:
        """Record the agent's planning decision."""
        self.record_event('planning', {
            'plan': plan,
            'reasoning': plan.get('reasoning', '')
        })

    def record_decision(self, decision_type: str, decision: str, reasoning: str) -> None:
        """
        Record a decision made by the agent.

        Args:
            decision_type: Type of decision (e.g., 'tool_selection', 'delegation')
            decision: The decision made
            reasoning: The reasoning behind the decision
        """
        self.record_event('decision', {
            'decision_type': decision_type,
            'decision': decision,
            'reasoning': reasoning
        })

    def record_delegation(self, target_agent: str, task: str, context: Dict[str, Any]) -> None:
        """
        Record a delegation to another agent.

        Args:
            target_agent: ID of the agent being delegated to
            task: Task being delegated
            context: Context passed to the target agent
        """
        self.record_event('delegation', {
            'target_agent': target_agent,
            'task': task,
            'context': context
        })

    def record_state_change(self, state_name: str, old_value: Any, new_value: Any) -> None:
        """
        Record a change in the agent's state.

        Args:
            state_name: Name of the state variable
            old_value: Previous value
            new_value: New value
        """
        self.record_event('state_change', {
            'state_name': state_name,
            'old_value': old_value,
            'new_value': new_value
        })

    def record_uncertainty(self, uncertainty_type: str, description: str) -> None:
        """
        Record uncertainty expressed by the agent.

        Args:
            uncertainty_type: Type of uncertainty (e.g., 'ambiguous_input', 'incomplete_info')
            description: Description of the uncertainty
        """
        self.record_event('uncertainty', {
            'uncertainty_type': uncertainty_type,
            'description': description
        })

    def record_error(self, error_type: str, error_message: str, recovered: bool) -> None:
        """
        Record an error encountered during execution.

        Args:
            error_type: Type of error (e.g., 'tool_failure', 'timeout')
            error_message: Error message
            recovered: Whether the agent recovered from the error
        """
        self.record_event('error', {
            'error_type': error_type,
            'error_message': error_message,
            'recovered': recovered
        })

    def record_approval_request(self, operation: str, reason: str) -> None:
        """
        Record a request for user approval.

        Args:
            operation: Operation requiring approval
            reason: Reason approval is required
        """
        self.record_event('approval_request', {
            'operation': operation,
            'reason': reason
        })

    def record_limitation(self, limitation_type: str, description: str) -> None:
        """
        Record a limitation the agent encountered.

        Args:
            limitation_type: Type of limitation (e.g., 'unsupported_language', 'missing_files')
            description: Description of the limitation
        """
        self.record_event('limitation', {
            'limitation_type': limitation_type,
            'description': description
        })

    def get_events_by_type(self, event_type: str) -> List[Dict[str, Any]]:
        """Get all events of a specific type."""
        return [event for event in self.trace if event['event_type'] == event_type]

    def get_planning_events(self) -> List[Dict[str, Any]]:
        """Get all planning events."""
        return self.get_events_by_type('planning')

    def get_decision_events(self) -> List[Dict[str, Any]]:
        """Get all decision events."""
        return self.get_events_by_type('decision')

    def get_delegation_events(self) -> List[Dict[str, Any]]:
        """Get all delegation events."""
        return self.get_events_by_type('delegation')

    def get_error_events(self) -> List[Dict[str, Any]]:
        """Get all error events."""
        return self.get_events_by_type('error')

    def get_uncertainty_events(self) -> List[Dict[str, Any]]:
        """Get all uncertainty events."""
        return self.get_events_by_type('uncertainty')

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the execution trace."""
        if not self.trace:
            return {
                'total_events': 0,
                'event_types': {},
                'duration_seconds': 0
            }

        # Count events by type
        event_types = {}
        for event in self.trace:
            event_type = event['event_type']
            event_types[event_type] = event_types.get(event_type, 0) + 1

        duration_seconds = 0
        if self.start_time and self.end_time:
            duration_seconds = (self.end_time - self.start_time).total_seconds()

        return {
            'agent_id': self.agent_id,
            'agent_version': self.agent_version,
            'model': self.model,
            'total_events': len(self.trace),
            'event_types': event_types,
            'duration_seconds': duration_seconds,
            'errors': len(self.get_error_events()),
            'uncertainties': len(self.get_uncertainty_events()),
            'delegations': len(self.get_delegation_events())
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert the entire trace to a dictionary."""
        return {
            'agent_id': self.agent_id,
            'agent_version': self.agent_version,
            'model': self.model,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'trace': self.trace,
            'summary': self.get_summary()
        }

    def save_to_file(self, filepath: str) -> None:
        """Save the trace to a JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


class TraceAnalyzer:
    """Analyzes agent traces to extract insights."""

    def __init__(self, trace: Dict[str, Any]):
        self.trace = trace

    def count_tool_selections(self) -> int:
        """Count the number of tool selection decisions."""
        decisions = self.trace.get('trace', [])
        return sum(1 for d in decisions if d.get('event_type') == 'decision' and d.get('data', {}).get('decision_type') == 'tool_selection')

    def count_delegations(self) -> int:
        """Count the number of delegations."""
        return len([e for e in self.trace.get('trace', []) if e.get('event_type') == 'delegation'])

    def count_uncertainties(self) -> int:
        """Count the number of uncertainties expressed."""
        return len([e for e in self.trace.get('trace', []) if e.get('event_type') == 'uncertainty'])

    def count_errors(self) -> int:
        """Count the number of errors encountered."""
        return len([e for e in self.trace.get('trace', []) if e.get('event_type') == 'error'])

    def count_recoveries(self) -> int:
        """Count the number of successful error recoveries."""
        errors = [e for e in self.trace.get('trace', []) if e.get('event_type') == 'error']
        return sum(1 for e in errors if e.get('data', {}).get('recovered', False))

    def get_delegated_agents(self) -> List[str]:
        """Get list of agents that were delegated to."""
        delegations = [e for e in self.trace.get('trace', []) if e.get('event_type') == 'delegation']
        return list(set([d.get('data', {}).get('target_agent') for d in delegations]))

    def get_uncertainty_types(self) -> List[str]:
        """Get list of uncertainty types encountered."""
        uncertainties = [e for e in self.trace.get('trace', []) if e.get('event_type') == 'uncertainty']
        return list(set([u.get('data', {}).get('uncertainty_type') for u in uncertainties]))

    def get_error_types(self) -> List[str]:
        """Get list of error types encountered."""
        errors = [e for e in self.trace.get('trace', []) if e.get('event_type') == 'error']
        return list(set([e.get('data', {}).get('error_type') for e in errors]))

    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive analysis report."""
        return {
            'agent_id': self.trace.get('agent_id'),
            'model': self.trace.get('model'),
            'duration_seconds': self.trace.get('summary', {}).get('duration_seconds', 0),
            'total_events': self.trace.get('summary', {}).get('total_events', 0),
            'tool_selections': self.count_tool_selections(),
            'delegations': self.count_delegations(),
            'delegated_agents': self.get_delegated_agents(),
            'uncertainties': self.count_uncertainties(),
            'uncertainty_types': self.get_uncertainty_types(),
            'errors': self.count_errors(),
            'error_types': self.get_error_types(),
            'recoveries': self.count_recoveries(),
            'recovery_rate': self.count_recoveries() / self.count_errors() if self.count_errors() > 0 else 1.0
        }
