import os
from pathlib import Path

ROOT = Path(__file__).parent

# Keep whatever model adk create gave you. For Claude, wrap it with LiteLlm in each agent instead.
MODEL = os.getenv('JARVIS_MODEL', 'gemini-3.5-flash')

# Every folder inside REPOSITORY_DIR is one code repository the VR UI can show.
REPOSITORY_DIR = Path(os.getenv('JARVIS_REPOSITORY_DIR', ROOT.parent.parent / 'repository')).resolve()
INDEX_DIR = ROOT / 'data' / 'index'      # generated graphs, one json per repository


def _initial_repo():
    want = os.getenv('JARVIS_REPO', '')
    if want:
        p = Path(want)
        return p if p.is_absolute() else REPOSITORY_DIR / want
    dirs = sorted(d for d in REPOSITORY_DIR.iterdir() if d.is_dir() and not d.name.startswith('.')) if REPOSITORY_DIR.is_dir() else []
    return dirs[0] if dirs else REPOSITORY_DIR / 'demo-account-service'


REPO_ROOT = _initial_repo()
GRAPH_PATH = INDEX_DIR / (REPO_ROOT.name + '.json')
CHANGE_PATH = ROOT / 'data' / 'demo_change.json'
MEMORY_PATH = ROOT / 'data' / 'project_memory.json'
CACHED_TESTS_PATH = ROOT / 'data' / 'cached_test_results.json'
WORKTREE_DIR = ROOT / 'work'

# Cached mode returns prepared test results. Use it for the judged demo.
USE_CACHED_TESTS = os.getenv('JARVIS_CACHED_TESTS', '1') == '1'
