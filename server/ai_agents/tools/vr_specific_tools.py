"""
VR-Specific Tools
Tools for interacting with software intelligence spatially in VR.
These are not UI design tools, but tools for interacting with software intelligence spatially.
"""

from typing import Optional, List, Dict, Any
import time
from google.adk.tools import ToolContext
from ._safe import safe

# In-memory VR state
_vr_session_state = {
    'active': False,
    'session_id': None,
    'started_at': None
}

_voice_commands = {}
_hand_interaction_mode = 'default'
_spatial_audio_settings = {}
_haptic_feedback_settings = {}
_vr_environment = 'default'
_theme = 'default'
_spatial_scale = 1.0
_camera_state = {'position': [0, 0, 0], 'rotation': [0, 0, 0]}
_scene_states = {}


@safe
def get_vr_session_state(tool_context: ToolContext) -> dict:
    """Understand the current VR session."""
    try:
        return {
            'status': 'ok',
            'session': _vr_session_state,
            'note': 'In-memory state - production requires Unity integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_selected_object(tool_context: ToolContext) -> dict:
    """Identify the currently selected code element or graph node."""
    try:
        from .visualization_spatial_tools import get_current_selection
        return get_current_selection(tool_context)
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Note: The following spatial tools are now in visualization_spatial_tools.py:
# - get_spatial_selection_context (delegates to get_spatial_selection_context)
# - select_code_element
# - focus_on_object
# - expand_relationships
# - trace_relationship_path
# - isolate_relationship_path
# - compare_code_regions
# - pin_investigation
# - restore_investigation
# - create_spatial_bookmark
# - annotate_code_element
# - synchronize_graphs
# - request_visualization
# - change_visualization_depth
# - change_visualization_scope
# - get_visualization_state
# - get_spatial_object_details
# These were removed from here to avoid duplicate tool names.
# Use the canonical versions from visualization_spatial_tools.py.


# Voice and Gesture Tools

@safe
def process_voice_command(
    command: str,
    tool_context: ToolContext
) -> dict:
    """Process a voice command."""
    try:
        # Check if command is registered
        if command in _voice_commands:
            return {
                'status': 'ok',
                'command': command,
                'action': _voice_commands[command],
                'executed': True,
                'note': 'In-memory processing - production requires Unity speech recognition'
            }
        return {
            'status': 'ok',
            'command': command,
            'executed': False,
            'message': 'Command not recognized or not registered',
            'note': 'In-memory processing - production requires Unity speech recognition'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def register_voice_command(
    command_text: str,
    action: str,
    tool_context: ToolContext
) -> dict:
    """Register a custom voice command."""
    try:
        _voice_commands[command_text] = action
        return {
            'status': 'ok',
            'command_text': command_text,
            'action': action,
            'registered': True,
            'note': 'In-memory registration - production requires Unity integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def list_voice_commands(tool_context: ToolContext) -> dict:
    """List registered voice commands."""
    try:
        return {
            'status': 'ok',
            'commands': list(_voice_commands.keys()),
            'count': len(_voice_commands),
            'note': 'In-memory listing - production requires Unity integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Hand Interaction Tools

@safe
def set_hand_interaction_mode(
    mode: str,
    tool_context: ToolContext
) -> dict:
    """Set hand interaction mode."""
    try:
        global _hand_interaction_mode
        _hand_interaction_mode = mode
        return {
            'status': 'ok',
            'mode': mode,
            'set': True,
            'note': 'In-memory setting - production requires Unity integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_hand_interaction_state(tool_context: ToolContext) -> dict:
    """Get current hand interaction state."""
    try:
        return {
            'status': 'ok',
            'mode': _hand_interaction_mode,
            'note': 'In-memory state - production requires Unity integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Spatial Audio Tools

@safe
def set_spatial_audio(
    source_id: str,
    position: Dict,
    tool_context: ToolContext
) -> dict:
    """Set spatial audio source."""
    try:
        _spatial_audio_settings[source_id] = position
        return {
            'status': 'ok',
            'source_id': source_id,
            'position': position,
            'set': True,
            'note': 'In-memory setting - production requires Unity integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def set_haptic_feedback(
    intensity: float,
    duration: float,
    tool_context: ToolContext
) -> dict:
    """Set haptic feedback."""
    try:
        _haptic_feedback_settings['intensity'] = intensity
        _haptic_feedback_settings['duration'] = duration
        return {
            'status': 'ok',
            'intensity': intensity,
            'duration': duration,
            'set': True,
            'note': 'In-memory setting - production requires Unity integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Environment Tools

@safe
def set_vr_environment(
    environment_id: str,
    tool_context: ToolContext
) -> dict:
    """Set VR environment."""
    try:
        global _vr_environment
        _vr_environment = environment_id
        return {
            'status': 'ok',
            'environment_id': environment_id,
            'set': True,
            'note': 'In-memory setting - production requires Unity integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_environment_info(
    environment_id: str,
    tool_context: ToolContext
) -> dict:
    """Get environment information."""
    try:
        current_env = environment_id if environment_id else _vr_environment
        return {
            'status': 'ok',
            'environment_id': current_env,
            'info': {
                'name': current_env,
                'type': 'vr_environment',
                'active': current_env == _vr_environment
            },
            'note': 'In-memory info - production requires Unity integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def set_theme(
    theme_id: str,
    tool_context: ToolContext
) -> dict:
    """Set visualization theme."""
    try:
        global _theme
        _theme = theme_id
        return {
            'status': 'ok',
            'theme_id': theme_id,
            'set': True,
            'note': 'In-memory setting - production requires Unity integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def set_layout_algorithm(
    algorithm: str,
    tool_context: ToolContext
) -> dict:
    """Set graph layout algorithm."""
    try:
        from .visualization_spatial_tools import calculate_graph_layout
        return calculate_graph_layout('default', tool_context, algorithm)
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def set_spatial_scaling(
    scale: float,
    tool_context: ToolContext
) -> dict:
    """Set spatial scaling."""
    try:
        global _spatial_scale
        _spatial_scale = scale
        return {
            'status': 'ok',
            'scale': scale,
            'set': True,
            'note': 'In-memory setting - production requires Unity integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def reset_camera(tool_context: ToolContext) -> dict:
    """Reset camera to default position."""
    try:
        global _camera_state
        _camera_state = {'position': [0, 0, 0], 'rotation': [0, 0, 0]}
        return {
            'status': 'ok',
            'camera_state': _camera_state,
            'reset': True,
            'note': 'In-memory reset - production requires Unity integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def save_scene_state(
    state_id: str,
    tool_context: ToolContext
) -> dict:
    """Save current scene state."""
    try:
        _scene_states[state_id] = {
            'environment': _vr_environment,
            'theme': _theme,
            'scale': _spatial_scale,
            'camera': _camera_state,
            'saved_at': time.time()
        }
        return {
            'status': 'ok',
            'state_id': state_id,
            'saved': True,
            'note': 'In-memory save - production requires Unity integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def load_scene_state(
    state_id: str,
    tool_context: ToolContext
) -> dict:
    """Load a saved scene state."""
    try:
        if state_id in _scene_states:
            state = _scene_states[state_id]
            global _vr_environment, _theme, _spatial_scale, _camera_state
            _vr_environment = state['environment']
            _theme = state['theme']
            _spatial_scale = state['scale']
            _camera_state = state['camera']
            return {
                'status': 'ok',
                'state_id': state_id,
                'loaded': True,
                'state': state,
                'note': 'In-memory load - production requires Unity integration'
            }
        return {
            'status': 'error',
            'error': f'State {state_id} not found'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Note: Additional spatial navigation tools removed:
# - focus_on_graph_node (use focus_on_object from visualization_spatial_tools)
# - set_graph_depth (use change_visualization_depth from visualization_spatial_tools)
# - navigate_to_code_element (use select_code_element from visualization_spatial_tools)
# These were removed to avoid duplicate tool names.
