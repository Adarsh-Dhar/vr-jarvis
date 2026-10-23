from google.adk.tools import ToolContext

from .scene_tools import show_approval_prompt


def request_approval(action_summary: str, tool_context: ToolContext) -> dict:
    '''Ask the user to approve a consequential action. Shows an approve or reject panel and
    returns immediately. The action may proceed only after state['approved'] becomes true.'''
    tool_context.state['pending_approval'] = action_summary
    tool_context.state['approved'] = False
    show_approval_prompt(action_summary, tool_context)
    return {'status': 'awaiting_user_approval'}


def exit_loop(tool_context: ToolContext) -> dict:
    '''Stop the enclosing verify loop. Call only when tests have passed.'''
    tool_context.actions.escalate = True
    return {'status': 'ok'}
