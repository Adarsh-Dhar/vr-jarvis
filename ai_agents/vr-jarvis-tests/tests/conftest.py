import logging
import os

os.environ.setdefault('JARVIS_CACHED_TESTS', '1')

import pytest  # noqa: E402

logging.getLogger('google_adk').setLevel(logging.ERROR)

from tests.harness.context import FakeToolContext, installed_graph  # noqa: E402


def pytest_collection_modifyitems(config, items):
    run_llm = os.getenv('JARVIS_RUN_LLM') == '1'
    run_soak = os.getenv('JARVIS_SOAK') == '1'
    for item in items:
        if 'llm' in item.keywords and not run_llm:
            item.add_marker(pytest.mark.skip(reason='set JARVIS_RUN_LLM=1 and model credentials to run'))
        if 'soak' in item.keywords and not run_soak:
            item.add_marker(pytest.mark.skip(reason='set JARVIS_SOAK=1 to run soak tests'))


@pytest.fixture
def env():
    with installed_graph() as e:
        yield e


@pytest.fixture
def git_env():
    with installed_graph(git=True) as e:
        yield e


@pytest.fixture
def ctx():
    return FakeToolContext()
