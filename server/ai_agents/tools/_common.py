import functools

MAX_EVIDENCE = 500


def record_evidence(tool_context, node_ids):
    '''Append node ids to state['evidence'] without duplicates, keeping only the most recent MAX_EVIDENCE.
    Reassigns so ADK sees the change.'''
    if tool_context is None:
        return  # No-op if no context (e.g., in tests)
    seen = list(tool_context.state.get('evidence', []))
    for node_id in node_ids:
        if node_id in seen:
            seen.remove(node_id)
        seen.append(node_id)
    tool_context.state['evidence'] = seen[-MAX_EVIDENCE:]


def repo_root():
    """Directory of the repository the tools currently work on (config.REPO_ROOT).
    Reads config.REPO_ROOT at call time, so a repository switch from the VR UI takes effect.
    Raises ValueError if the configured repository root does not exist."""
    from pathlib import Path
    from .. import config
    root = Path(config.REPO_ROOT)
    if not root.is_dir():
        raise ValueError(f"Configured repository root does not exist: {root}")
    return root


def resolve_in_repo(path, root=None):
    """Resolve a relative path against the repository root and ensure it stays inside.

    Args:
        path: A relative path (string or Path object)
        root: Optional root directory. If None, uses repo_root().

    Returns:
        Absolute Path object resolved against the repository root.

    Raises:
        ValueError: If the resolved path escapes the repository root.
    """
    from .path_resolver import resolve_repo_read
    from pathlib import Path
    return resolve_repo_read(path, root=Path(root) if root is not None else None)


def abs_repo_path(rel_path):
    """Absolute path of a graph node's file inside the ACTIVE repository (config.REPO_ROOT)."""
    if not rel_path:
        raise ValueError('Node has no file path')
    return resolve_in_repo(rel_path)


def heuristic(note):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            result = fn(*args, **kwargs)
            if isinstance(result, dict):
                result.setdefault('analysis_level', 'heuristic')
                result.setdefault('limitations', note)
            return result
        return wrapper
    return deco
