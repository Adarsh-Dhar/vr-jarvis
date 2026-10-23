import json
import subprocess
import uuid

from google.adk.tools import ToolContext

from ..config import CHANGE_PATH, REPO_ROOT, WORKTREE_DIR
from ._common import record_evidence


def _change():
    return json.loads(CHANGE_PATH.read_text())


def get_diff(tool_context: ToolContext) -> dict:
    '''Return the unified diff of the change under review, with its branch name.'''
    c = _change()
    return {'status': 'ok', 'branch': c['branch'], 'diff': c['diff']}


def list_changed_nodes(tool_context: ToolContext) -> dict:
    '''List graph node ids touched by the change under review.'''
    ids = _change()['changed_nodes']
    record_evidence(tool_context, ids)
    return {'status': 'ok', 'changed_nodes': ids}


def get_branch_info(tool_context: ToolContext) -> dict:
    '''Return branch, base branch and commit message of the change under review.'''
    c = _change()
    return {'status': 'ok', 'branch': c['branch'], 'base': c['base'], 'message': c['message']}


def create_worktree(tool_context: ToolContext, branch_name: str = 'jarvis/fix') -> dict:
    '''Create an isolated git worktree for a proposed patch. Never touches the main checkout.
    Stores the worktree path in session state.'''
    WORKTREE_DIR.mkdir(exist_ok=True)
    suffix = uuid.uuid4().hex[:6]
    path = WORKTREE_DIR / ('wt-' + suffix)
    proc = subprocess.run(
        ['git', 'worktree', 'add', '-b', branch_name + '-' + suffix, str(path)],
        cwd=REPO_ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        return {'status': 'error', 'stderr': proc.stderr[-1500:]}
    tool_context.state['worktree'] = str(path)
    return {'status': 'ok', 'worktree': str(path)}


def apply_patch_to_worktree(diff: str, tool_context: ToolContext) -> dict:
    '''Apply a unified diff inside the sandbox worktree. Fails if no worktree exists.
    Does not commit anything.'''
    wt = tool_context.state.get('worktree')
    if not wt:
        return {'status': 'error', 'error': 'Call create_worktree first.'}
    proc = subprocess.run(['git', 'apply', '--whitespace=nowarn', '-'],
                          input=diff, cwd=wt, capture_output=True, text=True)
    if proc.returncode != 0:
        return {'status': 'error', 'stderr': proc.stderr[-1500:]}
    return {'status': 'ok', 'applied': True}


def get_worktree_diff(tool_context: ToolContext) -> dict:
    '''Return the cumulative git diff of the sandbox worktree, including new files.'''
    wt = tool_context.state.get('worktree')
    if not wt:
        return {'status': 'error', 'error': 'No worktree yet.'}
    subprocess.run(['git', 'add', '-N', '.'], cwd=wt, capture_output=True, text=True)
    proc = subprocess.run(['git', 'diff', 'HEAD'], cwd=wt, capture_output=True, text=True)
    return {'status': 'ok', 'diff': proc.stdout}
