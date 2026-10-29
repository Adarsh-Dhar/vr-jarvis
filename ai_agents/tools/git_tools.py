import json
import re
import shutil
import subprocess
import threading
import uuid
from pathlib import Path

from google.adk.tools import ToolContext

from ..config import CHANGE_PATH, REPO_ROOT, WORKTREE_DIR
from ._common import record_evidence
from ._safe import safe

MAX_WORKTREES = 10          # oldest sandboxes are removed beyond this many
_LOCK = threading.Lock()
_PATH_RE = re.compile(r'^(?:diff --git a/(\S+) b/(\S+)|(?:---|\+\+\+) (?:a/|b/)?(\S+))', re.M)


def _change():
    return json.loads(CHANGE_PATH.read_text())


def _bad_diff_path(diff):
    '''Return the first path in a diff that is absolute, climbs out with .., or points into .git.'''
    for m in _PATH_RE.finditer(diff):
        for path in m.groups():
            if not path or path == '/dev/null' or path == 'dev/null':
                continue
            parts = path.split('/')
            if path.startswith('/') or '..' in parts or parts[0] == '.git':
                return path
    return None


def _prune_worktrees():
    trees = sorted(WORKTREE_DIR.glob('wt-*'), key=lambda p: p.stat().st_mtime)
    for old in trees[:max(len(trees) - MAX_WORKTREES, 0)]:
        subprocess.run(['git', 'worktree', 'remove', '--force', str(old)], cwd=REPO_ROOT, capture_output=True)
        shutil.rmtree(old, ignore_errors=True)
    subprocess.run(['git', 'worktree', 'prune'], cwd=REPO_ROOT, capture_output=True)


@safe
def get_diff(tool_context: ToolContext) -> dict:
    '''Return the unified diff of the change under review, with its branch name.'''
    c = _change()
    return {'status': 'ok', 'branch': c['branch'], 'diff': c['diff']}


@safe
def list_changed_nodes(tool_context: ToolContext) -> dict:
    '''List graph node ids touched by the change under review.'''
    ids = _change()['changed_nodes']
    record_evidence(tool_context, ids)
    return {'status': 'ok', 'changed_nodes': ids}


@safe
def get_branch_info(tool_context: ToolContext) -> dict:
    '''Return branch, base branch and commit message of the change under review.'''
    c = _change()
    return {'status': 'ok', 'branch': c['branch'], 'base': c['base'], 'message': c['message']}


@safe
def create_worktree(tool_context: ToolContext, branch_name: str = 'jarvis/fix') -> dict:
    '''Create an isolated git worktree for a proposed patch. Never touches the main checkout.
    Stores the worktree path in session state.'''
    WORKTREE_DIR.mkdir(exist_ok=True)
    suffix = uuid.uuid4().hex[:6]
    path = WORKTREE_DIR / ('wt-' + suffix)
    with _LOCK:
        proc = subprocess.run(
            ['git', 'worktree', 'add', '-b', branch_name + '-' + suffix, str(path)],
            cwd=REPO_ROOT, capture_output=True, text=True)
        if proc.returncode != 0:
            return {'status': 'error', 'stderr': proc.stderr[-1500:]}
        _prune_worktrees()
    nm = REPO_ROOT / 'node_modules'        # worktrees do not contain untracked node_modules
    if nm.is_dir() and not (path / 'node_modules').exists():
        (path / 'node_modules').symlink_to(nm, target_is_directory=True)
    tool_context.state['worktree'] = str(path)
    return {'status': 'ok', 'worktree': str(path)}


@safe
def apply_patch_to_worktree(diff: str, tool_context: ToolContext) -> dict:
    '''Apply a unified diff inside the sandbox worktree. Fails if no worktree exists.
    Does not commit anything.'''
    wt = tool_context.state.get('worktree')
    if not wt:
        return {'status': 'error', 'error': 'Call create_worktree first.'}
    bad = _bad_diff_path(diff)
    if bad:
        return {'status': 'error', 'error': 'Patch touches a path that is not allowed: ' + bad}
    proc = subprocess.run(['git', 'apply', '--whitespace=nowarn', '-'],
                          input=diff, cwd=wt, capture_output=True, text=True)
    if proc.returncode != 0:
        return {'status': 'error', 'stderr': proc.stderr[-1500:]}
    return {'status': 'ok', 'applied': True}


@safe
def get_worktree_diff(tool_context: ToolContext) -> dict:
    '''Return the cumulative git diff of the sandbox worktree, including new files.'''
    wt = tool_context.state.get('worktree')
    if not wt:
        return {'status': 'error', 'error': 'No worktree yet.'}
    subprocess.run(['git', 'add', '-N', '.'], cwd=wt, capture_output=True, text=True)
    proc = subprocess.run(['git', 'diff', 'HEAD'], cwd=wt, capture_output=True, text=True)
    return {'status': 'ok', 'diff': proc.stdout}


def commit_worktree(worktree: str, message: str) -> dict:
    '''Called only by the /approve endpoint after a human pinch-hold. Commits on the sandbox branch.
    Never merges into the main checkout. Not exposed to the model as a tool.'''
    if not worktree or not Path(worktree).is_dir():
        return {'ok': False, 'detail': 'No sandbox worktree to commit.'}
    subprocess.run(['git', 'add', '-A', '--', '.', ':!node_modules'], cwd=worktree, capture_output=True, text=True)
    c = subprocess.run(['git', '-c', 'user.name=JARVIS', '-c', 'user.email=jarvis@local', 'commit', '-m', message],
                       cwd=worktree, capture_output=True, text=True)
    if c.returncode != 0:
        return {'ok': False, 'detail': (c.stdout + c.stderr)[-400:]}
    sha = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=worktree, capture_output=True, text=True).stdout.strip()
    br = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=worktree, capture_output=True, text=True).stdout.strip()
    return {'ok': True, 'branch': br, 'commit': sha, 'detail': 'Committed on the sandbox branch. Main is untouched.'}
