import os
from pathlib import Path

from .llm import make_model

ROOT = Path(__file__).parent

# Models. Every agent gets MODEL (or LITE_MODEL) from here, wrapped so a call retries on overload (503/429) and can be paced.
# JARVIS_MODEL_LITE lets routine agents (critics, scene directors) use a cheaper model; it defaults to the same model.
# See ai_agents/llm.py for the JARVIS_LLM_* settings (retries, requests per minute, concurrency).
MODEL_NAME = os.getenv('JARVIS_MODEL', 'gemini-3.5-flash-lite')
LITE_MODEL_NAME = os.getenv('JARVIS_MODEL_LITE', MODEL_NAME)
MODEL = make_model(MODEL_NAME)
LITE_MODEL = make_model(LITE_MODEL_NAME)
MONTHLY_BUDGET_LIMIT = float(os.getenv('JARVIS_MONTHLY_BUDGET', '100.0'))  # USD

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
