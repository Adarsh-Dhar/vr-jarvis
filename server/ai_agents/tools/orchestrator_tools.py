"""
Agent 1 - JARVIS Orchestrator Tools
System-wide authority to coordinate other agents, decide which tools to invoke and combine their findings.
"""

from typing import Optional, List, Dict, Any
import re
import time
import uuid
from google.adk.tools import ToolContext
from ._safe import safe

# In-memory task state management
_task_state = {}
_agent_state = {}


@safe
def understand_user_intent(user_query: str, tool_context: ToolContext) -> dict:
    """Convert natural language into an actionable request."""
    try:
        query_lower = user_query.lower()
        
        # Simple keyword-based intent classification
        intent_keywords = {
            'debug_function': ['debug', 'fix', 'error', 'bug', 'broken'],
            'explain_code': ['explain', 'what does', 'how does', 'understand'],
            'find_definition': ['where is', 'find', 'locate', 'definition'],
            'analyze_performance': ['slow', 'performance', 'optimize', 'fast'],
            'security_scan': ['security', 'vulnerability', 'safe', 'injection'],
            'test_code': ['test', 'verify', 'check'],
            'refactor': ['refactor', 'clean', 'improve', 'rewrite'],
            'deploy': ['deploy', 'release', 'ship', 'publish']
        }
        
        # Find matching intent
        matched_intent = 'general_inquiry'
        confidence = 0.5
        entities = {}
        
        for intent, keywords in intent_keywords.items():
            matches = sum(1 for kw in keywords if kw in query_lower)
            if matches > 0:
                if matches > confidence:
                    matched_intent = intent
                    confidence = min(0.95, 0.5 + matches * 0.15)
        
        # Extract simple entities
        if 'function' in query_lower or 'def' in query_lower:
            func_match = re.search(r'(\w+)\s*(?:function|def)', user_query, re.IGNORECASE)
            if func_match:
                entities['function'] = func_match.group(1)
        
        if 'file' in query_lower or '.py' in user_query:
            file_match = re.search(r'([\w/\.]+\.py)', user_query)
            if file_match:
                entities['file'] = file_match.group(1)
        
        return {
            'status': 'ok',
            'intent': matched_intent,
            'confidence': confidence,
            'entities': entities
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def classify_request(user_query: str, tool_context: ToolContext) -> dict:
    """Determine whether the request is about code, debugging, visualization, security, etc."""
    try:
        query_lower = user_query.lower()
        
        categories = {
            'debugging': ['error', 'bug', 'crash', 'exception', 'trace', 'debug'],
            'code_understanding': ['explain', 'understand', 'what', 'how', 'why'],
            'visualization': ['show', 'visualize', 'graph', 'diagram', 'display'],
            'security': ['security', 'vulnerability', 'auth', 'permission', 'safe'],
            'testing': ['test', 'verify', 'check', 'assert'],
            'performance': ['slow', 'fast', 'performance', 'optimize', 'latency'],
            'refactoring': ['refactor', 'clean', 'improve', 'rewrite'],
            'deployment': ['deploy', 'release', 'ship', 'publish']
        }
        
        matched_category = 'general'
        subcategories = []
        confidence = 0.5
        
        for category, keywords in categories.items():
            matches = sum(1 for kw in keywords if kw in query_lower)
            if matches > 0:
                if matches > confidence:
                    matched_category = category
                    subcategories = [kw for kw in keywords if kw in query_lower]
                    confidence = min(0.95, 0.5 + matches * 0.1)
        
        return {
            'status': 'ok',
            'category': matched_category,
            'subcategories': subcategories,
            'confidence': confidence
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def create_investigation_plan(user_query: str, tool_context: ToolContext) -> dict:
    """Create a multi-step investigation."""
    try:
        # Get intent first
        intent_result = understand_user_intent(user_query, tool_context)
        if intent_result.get('status') != 'ok':
            return intent_result
        
        intent = intent_result['intent']
        
        # Define investigation plans based on intent
        plans = {
            'debug_function': [
                {'step': 1, 'agent': 'code_understanding', 'action': 'analyze_function'},
                {'step': 2, 'agent': 'runtime_intelligence', 'action': 'collect_trace'},
                {'step': 3, 'agent': 'debugging_intelligence', 'action': 'identify_root_cause'}
            ],
            'explain_code': [
                {'step': 1, 'agent': 'code_understanding', 'action': 'parse_code'},
                {'step': 2, 'agent': 'relationship_intelligence', 'action': 'trace_dependencies'},
                {'step': 3, 'agent': 'code_understanding', 'action': 'generate_explanation'}
            ],
            'find_definition': [
                {'step': 1, 'agent': 'code_understanding', 'action': 'search_symbols'},
                {'step': 2, 'agent': 'code_understanding', 'action': 'get_definition'},
                {'step': 3, 'agent': 'repository_intelligence', 'action': 'get_context'}
            ],
            'security_scan': [
                {'step': 1, 'agent': 'security_quality', 'action': 'scan_vulnerabilities'},
                {'step': 2, 'agent': 'security_quality', 'action': 'check_permissions'},
                {'step': 3, 'agent': 'security_quality', 'action': 'generate_report'}
            ]
        }
        
        plan = plans.get(intent, [
            {'step': 1, 'agent': 'code_understanding', 'action': 'analyze'},
            {'step': 2, 'agent': 'investigator', 'action': 'investigate'}
        ])
        
        return {
            'status': 'ok',
            'intent': intent,
            'plan': plan
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def decompose_task(task_description: str, tool_context: ToolContext) -> dict:
    """Break a task into independent subtasks."""
    try:
        # Simple task decomposition based on common patterns
        subtasks = []
        task_id = 0
        
        # Identify key action verbs
        if 'and' in task_description.lower():
            parts = re.split(r'\s+and\s+', task_description, flags=re.IGNORECASE)
            for part in parts:
                task_id += 1
                subtasks.append({
                    'id': f'subtask_{task_id}',
                    'description': part.strip(),
                    'dependencies': []
                })
        else:
            # Create a default decomposition
            task_id += 1
            subtasks.append({
                'id': f'subtask_{task_id}',
                'description': f'Analyze: {task_description}',
                'dependencies': []
            })
            task_id += 1
            subtasks.append({
                'id': f'subtask_{task_id}',
                'description': 'Execute primary action',
                'dependencies': [f'subtask_{task_id-1}']
            })
            task_id += 1
            subtasks.append({
                'id': f'subtask_{task_id}',
                'description': 'Verify results',
                'dependencies': [f'subtask_{task_id-1}']
            })
        
        return {
            'status': 'ok',
            'subtasks': subtasks
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def select_agents(task_description: str, tool_context: ToolContext) -> dict:
    """Select the appropriate specialist agents."""
    try:
        task_lower = task_description.lower()
        
        # Agent selection criteria
        agent_criteria = {
            'code_understanding': ['code', 'function', 'class', 'explain', 'understand', 'parse'],
            'repository_intelligence': ['repository', 'project', 'structure', 'dependencies'],
            'relationship_intelligence': ['relationship', 'dependency', 'call', 'import'],
            'data_flow_intelligence': ['data flow', 'variable', 'propagation'],
            'runtime_intelligence': ['runtime', 'execution', 'trace', 'log'],
            'debugging_intelligence': ['debug', 'error', 'bug', 'exception'],
            'security_quality': ['security', 'vulnerability', 'permission', 'safe'],
            'software_engineering': ['build', 'compile', 'format', 'refactor'],
            'testing_verification': ['test', 'verify', 'check', 'assert'],
            'visualization_spatial': ['visualize', 'graph', 'display', 'show']
        }
        
        selected_agents = []
        for agent, keywords in agent_criteria.items():
            matches = sum(1 for kw in keywords if kw in task_lower)
            if matches > 0:
                selected_agents.append({
                    'agent': agent,
                    'reason': f'Match on {matches} keywords: {", ".join([kw for kw in keywords if kw in task_lower])}'
                })
        
        # Always include code_understanding as baseline
        if not any(a['agent'] == 'code_understanding' for a in selected_agents):
            selected_agents.append({
                'agent': 'code_understanding',
                'reason': 'Baseline code analysis'
            })
        
        return {
            'status': 'ok',
            'selected_agents': selected_agents
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def delegate_task(
    agent_id: str,
    task: str,
    tool_context: ToolContext
) -> dict:
    """Assign tasks to other agents."""
    try:
        task_id = str(uuid.uuid4())
        
        _task_state[task_id] = {
            'agent_id': agent_id,
            'task': task,
            'status': 'assigned',
            'created_at': time.time(),
            'result': None
        }
        
        return {
            'status': 'ok',
            'agent_id': agent_id,
            'task_id': task_id,
            'task': task,
            'status': 'assigned'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def run_agents_parallel(task_ids: List[str], tool_context: ToolContext) -> dict:
    """Execute independent investigations concurrently."""
    try:
        # Update task states to running
        for task_id in task_ids:
            if task_id in _task_state:
                _task_state[task_id]['status'] = 'running'
                _task_state[task_id]['started_at'] = time.time()
        
        # Simulate parallel execution
        completion_times = {}
        for task_id in task_ids:
            completion_times[task_id] = 1.0 + (hash(task_id) % 300) / 100.0
            if task_id in _task_state:
                _task_state[task_id]['status'] = 'completed'
                _task_state[task_id]['completed_at'] = time.time()
                _task_state[task_id]['result'] = {'summary': 'Task completed'}
        
        return {
            'status': 'ok',
            'task_ids': task_ids,
            'parallel_execution': True,
            'completion_times': completion_times
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def run_agents_sequentially(task_ids: List[str], tool_context: ToolContext) -> dict:
    """Execute tasks with dependencies in order."""
    try:
        total_time = 0.0
        
        for task_id in task_ids:
            if task_id in _task_state:
                _task_state[task_id]['status'] = 'running'
                _task_state[task_id]['started_at'] = time.time()
                
                # Simulate execution time
                exec_time = 1.0 + (hash(task_id) % 200) / 100.0
                total_time += exec_time
                
                _task_state[task_id]['status'] = 'completed'
                _task_state[task_id]['completed_at'] = time.time()
                _task_state[task_id]['result'] = {'summary': 'Task completed'}
        
        return {
            'status': 'ok',
            'task_ids': task_ids,
            'sequential_execution': True,
            'completion_time': total_time
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def wait_for_agent(task_id: str, tool_context: ToolContext) -> dict:
    """Wait for delegated work to finish."""
    try:
        if task_id not in _task_state:
            return {
                'status': 'error',
                'error': f'Task {task_id} not found'
            }
        
        task = _task_state[task_id]
        
        # In a real implementation, this would block or poll
        # For now, return current state
        return {
            'status': 'ok',
            'task_id': task_id,
            'agent_status': task['status'],
            'result': task.get('result')
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_agent_status(task_id: str, tool_context: ToolContext) -> dict:
    """Check agent progress."""
    try:
        if task_id not in _task_state:
            return {
                'status': 'error',
                'error': f'Task {task_id} not found'
            }
        
        task = _task_state[task_id]
        
        # Calculate progress based on state
        status = task['status']
        progress = 0.0
        current_step = 'pending'
        
        if status == 'assigned':
            progress = 0.0
            current_step = 'pending'
        elif status == 'running':
            progress = 0.5
            current_step = 'executing'
        elif status == 'completed':
            progress = 1.0
            current_step = 'completed'
        
        return {
            'status': 'ok',
            'task_id': task_id,
            'agent_status': status,
            'progress': progress,
            'current_step': current_step
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def cancel_agent_task(task_id: str, tool_context: ToolContext) -> dict:
    """Stop unnecessary or incorrect work."""
    try:
        if task_id not in _task_state:
            return {
                'status': 'error',
                'error': f'Task {task_id} not found'
            }
        
        _task_state[task_id]['status'] = 'cancelled'
        _task_state[task_id]['cancelled_at'] = time.time()
        
        return {
            'status': 'ok',
            'task_id': task_id,
            'cancelled': True,
            'reason': 'User request'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def retry_agent_task(task_id: str, tool_context: ToolContext) -> dict:
    """Retry failed tasks."""
    try:
        if task_id not in _task_state:
            return {
                'status': 'error',
                'error': f'Task {task_id} not found'
            }
        
        task = _task_state[task_id]
        retry_count = task.get('retry_count', 0) + 1
        
        if retry_count > 3:
            return {
                'status': 'error',
                'error': f'Max retry attempts exceeded for task {task_id}'
            }
        
        _task_state[task_id]['retry_count'] = retry_count
        _task_state[task_id]['status'] = 'retrying'
        _task_state[task_id]['last_retry'] = time.time()
        
        return {
            'status': 'ok',
            'task_id': task_id,
            'retry_count': retry_count,
            'status': 'retrying'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def merge_agent_results(task_ids: List[str], tool_context: ToolContext) -> dict:
    """Combine findings from multiple agents."""
    try:
        results = []
        conflicts = []
        
        for task_id in task_ids:
            if task_id in _task_state:
                task = _task_state[task_id]
                if task.get('result'):
                    results.append(task['result'])
        
        # Simple conflict detection
        if len(results) > 1:
            # Check for conflicting summaries
            summaries = [r.get('summary', '') for r in results if 'summary' in r]
            if len(set(summaries)) > 1:
                conflicts.append({
                    'type': 'conflicting_summaries',
                    'details': summaries
                })
        
        merged_result = {
            'summary': f'Combined analysis from {len(results)} agents',
            'conflicts': conflicts,
            'confidence': 0.9 if not conflicts else 0.7,
            'source_count': len(results)
        }
        
        return {
            'status': 'ok',
            'task_ids': task_ids,
            'merged_result': merged_result
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def resolve_conflicting_findings(conflicts: List[Dict], tool_context: ToolContext) -> dict:
    """Investigate contradictory results."""
    try:
        resolved_count = 0
        resolutions = []
        
        for conflict in conflicts:
            conflict_type = conflict.get('type', 'unknown')
            
            if conflict_type == 'conflicting_summaries':
                # Prefer the most recent or most detailed result
                resolutions.append({
                    'type': conflict_type,
                    'resolution': 'Most recent result selected',
                    'confidence': 0.8
                })
                resolved_count += 1
            else:
                resolutions.append({
                    'type': conflict_type,
                    'resolution': 'Manual review required',
                    'confidence': 0.5
                })
        
        return {
            'status': 'ok',
            'conflicts_resolved': resolved_count,
            'resolutions': resolutions,
            'confidence': 0.75 if resolved_count > 0 else 0.5
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def request_more_evidence(
    task_id: str,
    evidence_type: str,
    tool_context: ToolContext
) -> dict:
    """Ask agents for stronger supporting evidence."""
    try:
        if task_id not in _task_state:
            return {
                'status': 'error',
                'error': f'Task {task_id} not found'
            }
        
        _task_state[task_id]['evidence_requested'] = {
            'type': evidence_type,
            'requested_at': time.time()
        }
        
        return {
            'status': 'ok',
            'task_id': task_id,
            'evidence_type': evidence_type,
            'evidence_requested': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def check_task_completion(task_id: str, tool_context: ToolContext) -> dict:
    """Verify that all required subtasks are complete."""
    try:
        if task_id not in _task_state:
            return {
                'status': 'error',
                'error': f'Task {task_id} not found'
            }
        
        task = _task_state[task_id]
        status = task['status']
        
        all_complete = status == 'completed'
        completion_percentage = 1.0 if all_complete else 0.5 if status == 'running' else 0.0
        
        return {
            'status': 'ok',
            'task_id': task_id,
            'all_subtasks_complete': all_complete,
            'completion_percentage': completion_percentage
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def request_user_approval(
    operation: str,
    description: str,
    tool_context: ToolContext
) -> dict:
    """Obtain approval for sensitive operations."""
    try:
        # This would typically integrate with a UI or approval system
        # For now, return pending state
        approval_id = str(uuid.uuid4())
        
        return {
            'status': 'pending_approval',
            'approval_id': approval_id,
            'operation': operation,
            'description': description,
            'approval_required': True,
            'requested_at': time.time()
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def manage_task_priority(task_ids: List[str], tool_context: ToolContext) -> dict:
    """Prioritize urgent investigations."""
    try:
        priorities = {}
        
        # Assign priorities based on task characteristics
        for i, task_id in enumerate(task_ids):
            if task_id in _task_state:
                task = _task_state[task_id]
                task_lower = task.get('task', '').lower()
                
                if 'urgent' in task_lower or 'critical' in task_lower:
                    priority = 'high'
                elif 'important' in task_lower:
                    priority = 'medium'
                else:
                    priority = 'low' if i > len(task_ids) // 2 else 'medium'
                
                priorities[task_id] = priority
                _task_state[task_id]['priority'] = priority
        
        # Reorder by priority
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        reordered = sorted(task_ids, key=lambda tid: priority_order.get(priorities.get(tid, 'medium'), 1))
        
        return {
            'status': 'ok',
            'reordered_tasks': reordered,
            'priorities': priorities
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }
