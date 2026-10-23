import os
from pathlib import Path

ROOT = Path(__file__).parent

# Keep whatever model adk create gave you. For Claude, wrap it with LiteLlm in each agent instead.
MODEL = os.getenv('JARVIS_MODEL', 'gemini-3.5-flash')

REPO_ROOT = Path(os.getenv('JARVIS_REPO', ROOT / 'demo_repo'))
GRAPH_PATH = ROOT / 'data' / 'graph.json'
CHANGE_PATH = ROOT / 'data' / 'demo_change.json'
MEMORY_PATH = ROOT / 'data' / 'project_memory.json'
CACHED_TESTS_PATH = ROOT / 'data' / 'cached_test_results.json'
WORKTREE_DIR = ROOT / 'work'

# Cached mode returns prepared test results. Use it for the judged demo.
USE_CACHED_TESTS = os.getenv('JARVIS_CACHED_TESTS', '1') == '1'
