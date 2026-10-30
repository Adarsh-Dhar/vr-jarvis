from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import os
import sys
import types

import pytest

# Import this focused module without ai_agents/__init__.py, which intentionally
# boots the full ADK agent graph and therefore needs the optional google-adk package.
_AGENT_DIR = Path(__file__).resolve().parents[1] / "ai_agents"
_PACKAGE = "_jarvis_repository_browser_test"
_package_module = types.ModuleType(_PACKAGE)
_package_module.__path__ = [str(_AGENT_DIR)]
sys.modules.setdefault(_PACKAGE, _package_module)
_spec = spec_from_file_location(_PACKAGE + ".repository", _AGENT_DIR / "repository.py")
repository = module_from_spec(_spec)
sys.modules[_spec.name] = repository
_spec.loader.exec_module(repository)


def _make_repo(tmp_path, monkeypatch):
    root = tmp_path / "repositories"
    repo = root / "sample"
    (repo / "src" / "nested").mkdir(parents=True)
    (repo / "src" / "nested" / "hello.ts").write_text("export const answer = 42;\n", encoding="utf-8")
    (repo / "README.md").write_text("# Sample\n", encoding="utf-8")
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "ignored.js").write_text("ignored", encoding="utf-8")
    monkeypatch.setattr(repository.config, "REPOSITORY_DIR", root)
    return root, repo


def test_tree_lists_directories_first_and_skips_dependency_folders(tmp_path, monkeypatch):
    _make_repo(tmp_path, monkeypatch)

    result = repository.list_tree("sample", "")

    assert result["repo"] == "sample"
    assert [item["name"] for item in result["entries"]] == ["src", "README.md"]
    assert result["entries"][0]["type"] == "directory"


def test_nested_file_can_be_read(tmp_path, monkeypatch):
    _make_repo(tmp_path, monkeypatch)

    result = repository.read_browser_file("sample", "src/nested/hello.ts")

    assert result["status"] == "ok"
    assert result["path"] == "src/nested/hello.ts"
    assert result["content"] == "export const answer = 42;\n"
    assert result["total_lines"] == 2
    assert result["truncated"] is False


@pytest.mark.parametrize("bad_path", ["../outside", "/etc/passwd", "src/../../outside", "src\\\\nested"])
def test_tree_rejects_paths_outside_repository(tmp_path, monkeypatch, bad_path):
    _make_repo(tmp_path, monkeypatch)

    with pytest.raises((ValueError, FileNotFoundError)):
        repository.list_tree("sample", bad_path)


def test_binary_files_are_not_opened(tmp_path, monkeypatch):
    _, repo = _make_repo(tmp_path, monkeypatch)
    (repo / "image.bin").write_bytes(b"\x00\x01\x02")

    with pytest.raises(ValueError, match="Binary files"):
        repository.read_browser_file("sample", "image.bin")


def test_symlink_is_not_browsable(tmp_path, monkeypatch):
    _, repo = _make_repo(tmp_path, monkeypatch)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    (repo / "linked").symlink_to(outside, target_is_directory=True)

    result = repository.list_tree("sample", "")
    assert "linked" not in [item["name"] for item in result["entries"]]
    with pytest.raises((ValueError, FileNotFoundError)):
        repository.read_browser_file("sample", "linked/secret.txt")


def test_browser_limits_large_files(tmp_path, monkeypatch):
    _, repo = _make_repo(tmp_path, monkeypatch)
    (repo / "large.txt").write_text("0123456789abcdef", encoding="utf-8")
    monkeypatch.setattr(repository, "MAX_BROWSER_FILE_BYTES", 8)

    result = repository.read_browser_file("sample", "large.txt")

    assert result["content"] == "01234567"
    assert result["size"] == 16
    assert result["truncated"] is True


def test_default_repository_directory_is_project_root_repository():
    if "JARVIS_REPOSITORY_DIR" in os.environ:
        pytest.skip("custom repository directory is configured")

    project_root = Path(__file__).resolve().parents[2]
    assert repository.config.REPOSITORY_DIR == (project_root / "repository").resolve()
