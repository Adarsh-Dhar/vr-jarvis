"""
Infrastructure Services
The underlying services that make the tool ecosystem possible.
"""

from typing import Optional, List, Dict, Any
import json
import time
import uuid
import subprocess
import random
from pathlib import Path
from google.adk.tools import ToolContext
from ._safe import safe

# In-memory permission and tool registry
_permission_store = {}
_tool_registry = {}
_agent_registry = {}
_graph_store = {}

# Additional in-memory stores for stub implementations
_approval_store = {}
_memory_store = {}
_knowledge_store = {}
_evidence_store = {}
_message_store = {}
_topic_subscriptions = {}
_telemetry_store = {}
_sandbox_store = {}
_workflow_store = {}
_indexing_store = {}
_rendering_store = {}


# Permission System

@safe
def check_permission(
    tool_name: str,
    agent_id: str,
    operation: str,
    tool_context: ToolContext
) -> dict:
    """Check if an agent has permission to use a tool."""
    try:
        key = f"{agent_id}:{tool_name}"
        permission = _permission_store.get(key, 'read')
        
        # Define permission levels hierarchy
        permission_levels = {'read': 1, 'analyze': 2, 'execute': 3, 'modify': 4}
        operation_levels = {
            'read': 1, 'analyze': 2, 'execute': 3, 'modify': 4,
            'view': 1, 'inspect': 2, 'run': 3, 'change': 4
        }
        
        required_level = operation_levels.get(operation, 1)
        granted_level = permission_levels.get(permission, 0)
        
        permitted = granted_level >= required_level
        
        return {
            'status': 'ok',
            'tool_name': tool_name,
            'agent_id': agent_id,
            'operation': operation,
            'permitted': permitted,
            'permission_level': permission,
            'required_level': operation
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def grant_permission(
    tool_name: str,
    agent_id: str,
    permission_level: str,
    tool_context: ToolContext
) -> dict:
    """Grant permission to an agent for a tool."""
    try:
        key = f"{agent_id}:{tool_name}"
        _permission_store[key] = permission_level
        
        return {
            'status': 'ok',
            'tool_name': tool_name,
            'agent_id': agent_id,
            'permission_level': permission_level,
            'granted': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def revoke_permission(
    tool_name: str,
    agent_id: str,
    tool_context: ToolContext
) -> dict:
    """Revoke permission from an agent for a tool."""
    try:
        key = f"{agent_id}:{tool_name}"
        if key in _permission_store:
            del _permission_store[key]
        
        return {
            'status': 'ok',
            'tool_name': tool_name,
            'agent_id': agent_id,
            'revoked': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def list_permissions(
    tool_context: ToolContext,
    agent_id: Optional[str] = None,
    tool_name: Optional[str] = None
) -> dict:
    """List permissions for agents or tools."""
    try:
        permissions = []
        
        for key, level in _permission_store.items():
            stored_agent_id, stored_tool_name = key.split(':')
            
            if agent_id and stored_agent_id != agent_id:
                continue
            if tool_name and stored_tool_name != tool_name:
                continue
            
            permissions.append({
                'agent_id': stored_agent_id,
                'tool_name': stored_tool_name,
                'permission_level': level
            })
        
        return {
            'status': 'ok',
            'agent_id': agent_id,
            'tool_name': tool_name,
            'permissions': permissions
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def set_permission_level(
    permission_level: str,
    tool_context: ToolContext
) -> dict:
    """Set the default permission level for operations."""
    try:
        # This would set a global default
        return {
            'status': 'ok',
            'permission_level': permission_level,
            'set': True,
            'note': 'Default permission level updated'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def request_approval(
    operation: str,
    description: str,
    tool_context: ToolContext
) -> dict:
    """Request approval for sensitive operations."""
    try:
        approval_id = str(uuid.uuid4())
        _approval_store[approval_id] = {
            'status': 'pending',
            'operation': operation,
            'description': description,
            'requested_at': time.time()
        }
        
        return {
            'status': 'pending_approval',
            'approval_id': approval_id,
            'operation': operation,
            'description': description,
            'requested_at': time.time()
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def check_approval_status(
    approval_id: str,
    tool_context: ToolContext
) -> dict:
    """Check if approval has been granted."""
    try:
        if approval_id in _approval_store:
            return {
                'status': 'ok',
                'approval_id': approval_id,
                'approval_status': _approval_store[approval_id].get('status', 'pending'),
                'granted_at': _approval_store[approval_id].get('granted_at'),
                'requested_at': _approval_store[approval_id].get('requested_at')
            }
        
        return {
            'status': 'not_found',
            'approval_id': approval_id,
            'message': 'Approval request not found'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Tool Registry

@safe
def register_tool(
    tool_name: str,
    tool_definition: Dict,
    tool_context: ToolContext
) -> dict:
    """Register a tool in the registry."""
    try:
        _tool_registry[tool_name] = tool_definition
        
        return {
            'status': 'ok',
            'tool_name': tool_name,
            'registered': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def unregister_tool(
    tool_name: str,
    tool_context: ToolContext
) -> dict:
    """Unregister a tool from the registry."""
    try:
        if tool_name in _tool_registry:
            del _tool_registry[tool_name]
        
        return {
            'status': 'ok',
            'tool_name': tool_name,
            'unregistered': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_tool_definition(
    tool_name: str,
    tool_context: ToolContext
) -> dict:
    """Get tool definition from registry."""
    try:
        if tool_name in _tool_registry:
            return {
                'status': 'ok',
                'tool_name': tool_name,
                'definition': _tool_registry[tool_name]
            }
        
        return {
            'status': 'not_found',
            'tool_name': tool_name,
            'message': 'Tool not found in registry'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def list_tools(
    tool_context: ToolContext,
    agent_id: Optional[str] = None,
    permission_level: Optional[str] = None
) -> dict:
    """List available tools, optionally filtered by agent or permission level."""
    try:
        tools = []
        
        for tool_name, definition in _tool_registry.items():
            if agent_id:
                key = f"{agent_id}:{tool_name}"
                perm = _permission_store.get(key, 'read')
                if permission_level and perm != permission_level:
                    continue
            
            tools.append({
                'name': tool_name,
                'definition': definition
            })
        
        return {
            'status': 'ok',
            'agent_id': agent_id,
            'permission_level': permission_level,
            'tools': tools
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def discover_tools(
    module_path: str,
    tool_context: ToolContext
) -> dict:
    """Discover tools in a module."""
    try:
        path = Path(module_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'Module path not found: {module_path}'
            }
        
        # Simple discovery - list Python files in the module
        discovered_tools = []
        if path.is_dir():
            for py_file in path.glob('**/*.py'):
                discovered_tools.append({
                    'file': str(py_file.relative_to(path.parent)),
                    'type': 'python_module'
                })
        elif path.is_file() and path.suffix == '.py':
            discovered_tools.append({
                'file': str(path.name),
                'type': 'python_module'
            })
        
        return {
            'status': 'ok',
            'module_path': module_path,
            'discovered_tools': discovered_tools,
            'count': len(discovered_tools)
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def update_tool_definition(
    tool_name: str,
    tool_definition: Dict,
    tool_context: ToolContext
) -> dict:
    """Update tool definition in registry."""
    try:
        if tool_name in _tool_registry:
            _tool_registry[tool_name] = tool_definition
            return {
                'status': 'ok',
                'tool_name': tool_name,
                'updated': True
            }
        
        return {
            'status': 'not_found',
            'tool_name': tool_name,
            'message': 'Tool not found in registry'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Universal Code Intelligence Graph

@safe
def store_graph_node(
    node_id: str,
    node_data: Dict,
    tool_context: ToolContext
) -> dict:
    """Store a node in the code graph."""
    try:
        _graph_store[node_id] = node_data
        
        return {
            'status': 'ok',
            'node_id': node_id,
            'stored': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def store_graph_edge(
    from_id: str,
    to_id: str,
    edge_data: Dict,
    tool_context: ToolContext
) -> dict:
    """Store an edge in the code graph."""
    try:
        edge_key = f"{from_id}->{to_id}"
        _graph_store[edge_key] = edge_data
        
        return {
            'status': 'ok',
            'from_id': from_id,
            'to_id': to_id,
            'stored': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_graph_node(
    node_id: str,
    tool_context: ToolContext
) -> dict:
    """Retrieve a node from the code graph."""
    try:
        if node_id in _graph_store:
            return {
                'status': 'ok',
                'node_id': node_id,
                'node_data': _graph_store[node_id]
            }
        
        return {
            'status': 'not_found',
            'node_id': node_id,
            'message': 'Node not found in graph'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def query_graph(
    query: str,
    tool_context: ToolContext
) -> dict:
    """Query the code graph."""
    try:
        # Simple query parsing for in-memory graph
        # Supports basic queries like "get node <id>" or "get edges from <id>"
        results = []
        
        query_lower = query.lower()
        
        if 'get node' in query_lower:
            # Extract node ID from query
            parts = query.split()
            if len(parts) >= 3:
                node_id = parts[2]
                if node_id in _graph_store:
                    results.append({
                        'type': 'node',
                        'id': node_id,
                        'data': _graph_store[node_id]
                    })
        
        elif 'get edges' in query_lower:
            # Get all edges
            for key, value in _graph_store.items():
                if '->' in key:
                    results.append({
                        'type': 'edge',
                        'key': key,
                        'data': value
                    })
        
        elif 'from' in query_lower:
            # Get edges from a specific node
            parts = query.split()
            from_idx = parts.index('from')
            if from_idx + 1 < len(parts):
                from_id = parts[from_idx + 1]
                for key, value in _graph_store.items():
                    if key.startswith(f"{from_id}->"):
                        results.append({
                            'type': 'edge',
                            'key': key,
                            'data': value
                        })
        
        else:
            # Return all nodes
            for key, value in _graph_store.items():
                if '->' not in key:
                    results.append({
                        'type': 'node',
                        'id': key,
                        'data': value
                    })
        
        return {
            'status': 'ok',
            'query': query,
            'results': results,
            'count': len(results)
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def delete_graph_node(
    node_id: str,
    tool_context: ToolContext
) -> dict:
    """Delete a node from the code graph."""
    try:
        if node_id in _graph_store:
            del _graph_store[node_id]
        
        return {
            'status': 'ok',
            'node_id': node_id,
            'deleted': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def delete_graph_edge(
    from_id: str,
    to_id: str,
    tool_context: ToolContext
) -> dict:
    """Delete an edge from the code graph."""
    try:
        edge_key = f"{from_id}->{to_id}"
        if edge_key in _graph_store:
            del _graph_store[edge_key]
        
        return {
            'status': 'ok',
            'from_id': from_id,
            'to_id': to_id,
            'deleted': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def clear_graph(tool_context: ToolContext) -> dict:
    """Clear the entire code graph."""
    try:
        _graph_store.clear()
        
        return {
            'status': 'ok',
            'cleared': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Indexing Service

@safe
def start_indexing(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Start indexing a repository."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'Repository not found: {repository_path}'
            }
        
        # Create indexing job
        job_id = str(uuid.uuid4())
        _indexing_store[job_id] = {
            'repository_path': str(path),
            'status': 'in_progress',
            'started_at': time.time(),
            'files_indexed': 0
        }
        
        # Count files
        file_count = 0
        for item in path.rglob('*'):
            if item.is_file():
                file_count += 1
        
        _indexing_store[job_id]['total_files'] = file_count
        _indexing_store[job_id]['files_indexed'] = file_count
        _indexing_store[job_id]['status'] = 'completed'
        _indexing_store[job_id]['completed_at'] = time.time()
        
        return {
            'status': 'ok',
            'job_id': job_id,
            'repository_path': repository_path,
            'total_files': file_count,
            'status': 'completed'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_index_status(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Get indexing status."""
    try:
        # Find job for this repository
        for job_id, job_data in _indexing_store.items():
            if job_data.get('repository_path') == repository_path:
                return {
                    'status': 'ok',
                    'job_id': job_id,
                    'repository_path': repository_path,
                    'index_status': job_data.get('status'),
                    'files_indexed': job_data.get('files_indexed', 0),
                    'total_files': job_data.get('total_files', 0),
                    'started_at': job_data.get('started_at'),
                    'completed_at': job_data.get('completed_at')
                }
        
        return {
            'status': 'not_found',
            'repository_path': repository_path,
            'message': 'No indexing job found for this repository'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def update_index(
    repository_path: str,
    changed_files: List[str],
    tool_context: ToolContext
) -> dict:
    """Update index for changed files."""
    try:
        # Find existing job or create new one
        job_id = None
        for jid, job_data in _indexing_store.items():
            if job_data.get('repository_path') == repository_path:
                job_id = jid
                break
        
        if job_id:
            _indexing_store[job_id]['files_indexed'] += len(changed_files)
            _indexing_store[job_id]['last_updated'] = time.time()
            _indexing_store[job_id]['recent_changes'] = changed_files
        else:
            job_id = str(uuid.uuid4())
            _indexing_store[job_id] = {
                'repository_path': repository_path,
                'status': 'in_progress',
                'started_at': time.time(),
                'files_indexed': len(changed_files),
                'total_files': len(changed_files),
                'recent_changes': changed_files
            }
        
        return {
            'status': 'ok',
            'job_id': job_id,
            'repository_path': repository_path,
            'updated_files': len(changed_files),
            'changed_files': changed_files
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Agent Runtime

@safe
def start_agent(
    agent_id: str,
    agent_config: Dict,
    tool_context: ToolContext
) -> dict:
    """Start an agent instance."""
    try:
        _agent_registry[agent_id] = {
            'config': agent_config,
            'status': 'running',
            'started_at': time.time()
        }
        
        return {
            'status': 'ok',
            'agent_id': agent_id,
            'started': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def stop_agent(
    agent_id: str,
    tool_context: ToolContext
) -> dict:
    """Stop an agent instance."""
    try:
        if agent_id in _agent_registry:
            _agent_registry[agent_id]['status'] = 'stopped'
            _agent_registry[agent_id]['stopped_at'] = time.time()
        
        return {
            'status': 'ok',
            'agent_id': agent_id,
            'stopped': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def list_agents(
    tool_context: ToolContext,
    status: Optional[str] = None
) -> dict:
    """List agent instances."""
    try:
        agents = []
        for agent_id, agent_data in _agent_registry.items():
            if status and agent_data.get('status') != status:
                continue
            agents.append({
                'agent_id': agent_id,
                'status': agent_data.get('status', 'unknown'),
                'started_at': agent_data.get('started_at')
            })
        
        return {
            'status': 'ok',
            'agents': agents
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_agent_state(
    agent_id: str,
    tool_context: ToolContext
) -> dict:
    """Get agent state."""
    try:
        if agent_id in _agent_registry:
            return {
                'status': 'ok',
                'agent_id': agent_id,
                'state': _agent_registry[agent_id]
            }
        
        return {
            'status': 'not_found',
            'agent_id': agent_id,
            'message': 'Agent not found'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def send_message_to_agent(
    agent_id: str,
    message: Dict,
    tool_context: ToolContext
) -> dict:
    """Send a message to an agent."""
    try:
        if agent_id not in _agent_registry:
            return {
                'status': 'error',
                'error': f'Agent {agent_id} not found'
            }
        
        # This would send a message to the agent's message queue
        return {
            'status': 'ok',
            'agent_id': agent_id,
            'message_sent': True,
            'note': 'Message delivery requires agent message queue'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_agent_messages(
    agent_id: str,
    tool_context: ToolContext
) -> dict:
    """Get messages for an agent."""
    try:
        # Use in-memory message store
        messages = _message_store.get(agent_id, [])
        
        return {
            'status': 'ok',
            'agent_id': agent_id,
            'messages': messages,
            'count': len(messages)
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Message Bus

@safe
def publish_message(
    topic: str,
    message: Dict,
    tool_context: ToolContext
) -> dict:
    """Publish a message to a topic."""
    try:
        # This would publish to a message bus (RabbitMQ, Kafka, etc.)
        return {
            'status': 'ok',
            'topic': topic,
            'message_published': True,
            'note': 'Message bus requires external service integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def subscribe_to_topic(
    topic: str,
    callback: str,
    tool_context: ToolContext
) -> dict:
    """Subscribe to a topic."""
    try:
        # Use in-memory subscription store
        if topic not in _topic_subscriptions:
            _topic_subscriptions[topic] = []
        
        _topic_subscriptions[topic].append(callback)
        
        return {
            'status': 'ok',
            'topic': topic,
            'callback': callback,
            'subscribed': True,
            'note': 'In-memory subscription - production requires message bus integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def unsubscribe_from_topic(
    topic: str,
    tool_context: ToolContext
) -> dict:
    """Unsubscribe from a topic."""
    try:
        if topic in _topic_subscriptions:
            _topic_subscriptions[topic] = []
        
        return {
            'status': 'ok',
            'topic': topic,
            'unsubscribed': True,
            'note': 'In-memory subscription - production requires message bus integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Workflow Orchestration

@safe
def create_workflow(
    workflow_name: str,
    steps: List[Dict],
    tool_context: ToolContext
) -> dict:
    """Create a workflow."""
    try:
        workflow_id = str(uuid.uuid4())
        
        return {
            'status': 'ok',
            'workflow_id': workflow_id,
            'workflow_name': workflow_name,
            'steps': steps,
            'created': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def execute_workflow(
    workflow_id: str,
    tool_context: ToolContext
) -> dict:
    """Execute a workflow."""
    try:
        # Use in-memory workflow store
        if workflow_id in _workflow_store:
            workflow = _workflow_store[workflow_id]
            workflow['status'] = 'running'
            workflow['started_at'] = time.time()
        else:
            return {
                'status': 'error',
                'error': f'Workflow {workflow_id} not found'
            }
        
        return {
            'status': 'ok',
            'workflow_id': workflow_id,
            'executing': True,
            'note': 'In-memory execution - production requires orchestration engine'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_workflow_status(
    workflow_id: str,
    tool_context: ToolContext
) -> dict:
    """Get workflow execution status."""
    try:
        if workflow_id in _workflow_store:
            workflow = _workflow_store[workflow_id]
            return {
                'status': 'ok',
                'workflow_id': workflow_id,
                'workflow_status': workflow.get('status', 'unknown'),
                'created_at': workflow.get('created_at'),
                'started_at': workflow.get('started_at')
            }
        else:
            return {
                'status': 'error',
                'error': f'Workflow {workflow_id} not found'
            }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Memory Service

@safe
def store_memory(
    key: str,
    value: Any,
    tool_context: ToolContext
) -> dict:
    """Store a value in memory."""
    try:
        _memory_store[key] = {
            'value': value,
            'stored_at': time.time()
        }
        
        return {
            'status': 'ok',
            'key': key,
            'stored': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def retrieve_memory(
    key: str,
    tool_context: ToolContext
) -> dict:
    """Retrieve a value from memory."""
    try:
        if key in _memory_store:
            return {
                'status': 'ok',
                'key': key,
                'value': _memory_store[key]['value'],
                'stored_at': _memory_store[key]['stored_at']
            }
        
        return {
            'status': 'not_found',
            'key': key,
            'message': 'Key not found in memory store'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def delete_memory(
    key: str,
    tool_context: ToolContext
) -> dict:
    """Delete a value from memory."""
    try:
        if key in _memory_store:
            del _memory_store[key]
            return {
                'status': 'ok',
                'key': key,
                'deleted': True
            }
        
        return {
            'status': 'not_found',
            'key': key,
            'message': 'Key not found in memory store'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Telemetry Service

@safe
def start_telemetry_collection(
    collection_id: str,
    metrics: List[str],
    tool_context: ToolContext
) -> dict:
    """Start collecting telemetry data."""
    try:
        _telemetry_store[collection_id] = {
            'metrics': metrics,
            'status': 'collecting',
            'started_at': time.time(),
            'data_points': []
        }
        
        return {
            'status': 'ok',
            'collection_id': collection_id,
            'metrics': metrics,
            'collecting': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_telemetry_data(
    collection_id: str,
    tool_context: ToolContext,
    time_range: str = '1h'
) -> dict:
    """Get collected telemetry data."""
    try:
        if collection_id in _telemetry_store:
            # Generate some sample telemetry data
            sample_data = []
            for metric in _telemetry_store[collection_id]['metrics']:
                sample_data.append({
                    'metric': metric,
                    'value': random.uniform(0, 100),
                    'timestamp': time.time()
                })
            
            return {
                'status': 'ok',
                'collection_id': collection_id,
                'time_range': time_range,
                'data': sample_data,
                'metrics_collected': len(sample_data)
            }
        
        return {
            'status': 'not_found',
            'collection_id': collection_id,
            'message': 'Telemetry collection not found'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def stop_telemetry_collection(
    collection_id: str,
    tool_context: ToolContext
) -> dict:
    """Stop collecting telemetry data."""
    try:
        if collection_id in _telemetry_store:
            _telemetry_store[collection_id]['status'] = 'stopped'
            _telemetry_store[collection_id]['stopped_at'] = time.time()
            
            return {
                'status': 'ok',
                'collection_id': collection_id,
                'stopped': True
            }
        
        return {
            'status': 'not_found',
            'collection_id': collection_id,
            'message': 'Telemetry collection not found'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Sandbox Execution

@safe
def create_sandbox(
    sandbox_id: str,
    configuration: Dict,
    tool_context: ToolContext
) -> dict:
    """Create a sandbox for code execution."""
    try:
        _sandbox_store[sandbox_id] = {
            'configuration': configuration,
            'status': 'created',
            'created_at': time.time(),
            'command_history': []
        }
        
        return {
            'status': 'ok',
            'sandbox_id': sandbox_id,
            'created': True,
            'configuration': configuration
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def execute_in_sandbox(
    sandbox_id: str,
    command: str,
    tool_context: ToolContext
) -> dict:
    """Execute a command in a sandbox."""
    try:
        if sandbox_id not in _sandbox_store:
            return {
                'status': 'error',
                'error': f'Sandbox {sandbox_id} not found'
            }
        
        # Execute command using subprocess
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            output = {
                'stdout': result.stdout,
                'stderr': result.stderr,
                'return_code': result.returncode
            }
            
            _sandbox_store[sandbox_id]['command_history'].append({
                'command': command,
                'output': output,
                'timestamp': time.time()
            })
            
            return {
                'status': 'ok',
                'sandbox_id': sandbox_id,
                'command': command,
                'output': output,
                'executed': True
            }
        except subprocess.TimeoutExpired:
            return {
                'status': 'error',
                'error': 'Command execution timed out',
                'sandbox_id': sandbox_id,
                'command': command
            }
        except Exception as cmd_error:
            return {
                'status': 'error',
                'error': str(cmd_error),
                'sandbox_id': sandbox_id,
                'command': command
            }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def destroy_sandbox(
    sandbox_id: str,
    tool_context: ToolContext
) -> dict:
    """Destroy a sandbox."""
    try:
        if sandbox_id in _sandbox_store:
            del _sandbox_store[sandbox_id]
            
            return {
                'status': 'ok',
                'sandbox_id': sandbox_id,
                'destroyed': True
            }
        
        return {
            'status': 'not_found',
            'sandbox_id': sandbox_id,
            'message': 'Sandbox not found'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Evidence Service

@safe
def record_evidence(
    tool_context: ToolContext,
    node_ids: List[str]
) -> dict:
    """Record evidence for findings."""
    try:
        evidence_id = str(uuid.uuid4())
        _evidence_store[evidence_id] = {
            'node_ids': node_ids,
            'recorded_at': time.time(),
            'investigation_id': None
        }
        
        return {
            'status': 'ok',
            'evidence_id': evidence_id,
            'node_ids': node_ids,
            'recorded': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_evidence(
    investigation_id: str,
    tool_context: ToolContext
) -> dict:
    """Get evidence for an investigation."""
    try:
        evidence_list = []
        for evidence_id, evidence_data in _evidence_store.items():
            if evidence_data.get('investigation_id') == investigation_id:
                evidence_list.append({
                    'evidence_id': evidence_id,
                    'data': evidence_data
                })
        
        return {
            'status': 'ok',
            'investigation_id': investigation_id,
            'evidence': evidence_list,
            'count': len(evidence_list)
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def verify_evidence(
    evidence_id: str,
    tool_context: ToolContext
) -> dict:
    """Verify that evidence is still valid."""
    try:
        if evidence_id in _evidence_store:
            # Check if nodes still exist in graph
            node_ids = _evidence_store[evidence_id].get('node_ids', [])
            all_valid = True
            for node_id in node_ids:
                if node_id not in _graph_store:
                    all_valid = False
                    break
            
            return {
                'status': 'ok',
                'evidence_id': evidence_id,
                'valid': all_valid,
                'node_ids': node_ids,
                'verified_at': time.time()
            }
        
        return {
            'status': 'not_found',
            'evidence_id': evidence_id,
            'message': 'Evidence not found'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# VR Rendering Service

@safe
def render_graph(
    graph_id: str,
    tool_context: ToolContext
) -> dict:
    """Render a graph for VR display."""
    try:
        if graph_id in _graph_store:
            graph = _graph_store[graph_id]
            _rendering_store[graph_id] = {
                'status': 'rendering',
                'graph': graph,
                'started_at': time.time()
            }
            return {
                'status': 'ok',
                'graph_id': graph_id,
                'rendering': True,
                'note': 'In-memory rendering - production requires VR rendering engine'
            }
        return {
            'status': 'error',
            'error': f'Graph {graph_id} not found'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def update_rendering(
    graph_id: str,
    updates: List[Dict],
    tool_context: ToolContext
) -> dict:
    """Update the VR rendering."""
    try:
        if graph_id in _rendering_store:
            _rendering_store[graph_id]['updates'] = updates
            return {
                'status': 'ok',
                'graph_id': graph_id,
                'updated': True,
                'updates_count': len(updates)
            }
        return {
            'status': 'error',
            'error': f'Rendering {graph_id} not found'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_rendering_state(
    graph_id: str,
    tool_context: ToolContext
) -> dict:
    """Get the current rendering state."""
    try:
        if graph_id in _rendering_store:
            rendering = _rendering_store[graph_id]
            return {
                'status': 'ok',
                'graph_id': graph_id,
                'rendering_state': rendering.get('status', 'unknown'),
                'started_at': rendering.get('started_at'),
                'updates': rendering.get('updates', [])
            }
        return {
            'status': 'error',
            'error': f'Rendering {graph_id} not found'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }



