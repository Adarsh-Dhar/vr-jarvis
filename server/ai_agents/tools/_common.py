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
    from pathlib import Path
    
    if root is None:
        root = repo_root()
    else:
        root = Path(root)
    
    # Convert to Path if needed
    if not isinstance(path, Path):
        path = Path(path)
    
    # Resolve the path against the root
    resolved = (root / path).resolve()
    
    # Ensure the resolved path is inside the root (no symlink escapes)
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        raise ValueError(f"Path {path} resolves outside repository root: {resolved}")
    
    return resolved


def abs_repo_path(rel_path):
    """Absolute path of a graph node's file inside the ACTIVE repository (config.REPO_ROOT)."""
    if not rel_path:
        raise ValueError('Node has no file path')
    return resolve_in_repo(rel_path)
