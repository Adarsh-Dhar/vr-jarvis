"""Centralized path resolution with per-use policies.

Every tool that turns a user- or model-supplied path into a filesystem
access must go through ``resolve`` with an explicit ``PathPolicy``. The
resolver is the single place that decides which roots a path may live
under and which prefixes are forbidden; call sites never re-implement
containment checks.

Policies:

- ``REPO_READ`` / ``REPO_WRITE`` — inside ``config.REPO_ROOT``.
- ``WORKTREE_READ`` / ``WORKTREE_WRITE`` — inside the session sandbox
  worktree (``tool_context.state['worktree']``); writes additionally
  reject ``.git`` and ``node_modules`` (a symlink back to the main
  checkout).
- ``VR_ROOT`` — inside a VR-registered repository/file root.

Absolute paths are only accepted when they already live under the
policy's root; everything else is resolved relative to that root.
"""
import enum
from pathlib import Path
from typing import Optional


class PathPolicy(enum.Enum):
    REPO_READ = 'repo_read'
    REPO_WRITE = 'repo_write'
    WORKTREE_READ = 'worktree_read'
    WORKTREE_WRITE = 'worktree_write'
    VR_ROOT = 'vr_root'


# Top-level entries that must never be read or written through the
# worktree policy: .git holds the real repository metadata and
# node_modules is a symlink into the main checkout.
_WORKTREE_DENY = {'.git', 'node_modules'}


class PathResolutionError(ValueError):
    """Raised when a path violates the requested policy."""


def _repo_root() -> Path:
    from ..tools._common import repo_root
    return repo_root()


def _worktree_root(tool_context) -> Path:
    wt = (getattr(tool_context, 'state', None) or {}).get('worktree') \
        if tool_context is not None else None
    if not wt:
        raise PathResolutionError(
            'No sandbox worktree. Call create_worktree first.')
    root = Path(wt)
    if not root.is_dir():
        raise PathResolutionError(
            'Sandbox worktree does not exist: %s' % root)
    return root


def _vr_roots() -> list:
    """Registered VR-accessible roots (repositories/files the UI opened)."""
    roots = []
    try:
        from .. import config
        for attr in ('REPO_ROOT', 'REPOSITORY_DIR'):
            val = getattr(config, attr, None)
            if val:
                p = Path(val)
                if p.is_dir():
                    roots.append(p.resolve())
    except Exception:
        pass
    return roots


def _containment_root(policy: PathPolicy, tool_context=None) -> Path:
    if policy in (PathPolicy.REPO_READ, PathPolicy.REPO_WRITE):
        return _repo_root().resolve()
    if policy in (PathPolicy.WORKTREE_READ, PathPolicy.WORKTREE_WRITE):
        return _worktree_root(tool_context).resolve()
    if policy is PathPolicy.VR_ROOT:
        roots = _vr_roots()
        if not roots:
            raise PathResolutionError('No VR repository root is registered')
        return roots[0]
    raise PathResolutionError('Unknown path policy: %r' % policy)


def _resolve_under(raw, root: Path, policy: PathPolicy) -> Path:
    path = raw if isinstance(raw, Path) else Path(str(raw))
    if not path.is_absolute():
        candidate = (root / path)
    else:
        candidate = path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        raise PathResolutionError(
            'Path %r resolves outside the allowed root %s: %s'
            % (raw, policy.value, resolved))
    if policy in (PathPolicy.WORKTREE_WRITE, PathPolicy.REPO_WRITE):
        rel = resolved.relative_to(root)
        if rel.parts and rel.parts[0] in _WORKTREE_DENY:
            raise PathResolutionError(
                'Path %r is not writable under policy %s'
                % (raw, policy.value))
    return resolved


def resolve(raw, policy: PathPolicy, tool_context=None,
            root: Optional[Path] = None) -> Path:
    """Resolve ``raw`` under the root required by ``policy``.

    ``root`` may override the policy's default root (used by tests and by
    callers that already know the sandbox directory). For VR_ROOT the
    path must live under ANY registered VR root, not just the first.
    """
    if policy is PathPolicy.VR_ROOT and root is None:
        path = raw if isinstance(raw, Path) else Path(str(raw))
        candidate = path if path.is_absolute() else None
        roots = _vr_roots()
        if candidate is not None:
            resolved = candidate.resolve()
            for r in roots:
                try:
                    resolved.relative_to(r)
                    return resolved
                except ValueError:
                    continue
        if candidate is None and roots:
            # Relative path: resolve against the first VR root.
            return _resolve_under(raw, roots[0], policy)
        raise PathResolutionError(
            'Path %r is outside every registered VR root' % (raw,))
    base = Path(root).resolve() if root is not None \
        else _containment_root(policy, tool_context)
    return _resolve_under(raw, base, policy)


def resolve_repo_read(raw, root=None) -> Path:
    return resolve(raw, PathPolicy.REPO_READ, root=root)


def resolve_repo_write(raw, root=None) -> Path:
    return resolve(raw, PathPolicy.REPO_WRITE, root=root)


def resolve_worktree_read(raw, tool_context=None, root=None) -> Path:
    return resolve(raw, PathPolicy.WORKTREE_READ,
                   tool_context=tool_context, root=root)


def resolve_worktree_write(raw, tool_context=None, root=None) -> Path:
    return resolve(raw, PathPolicy.WORKTREE_WRITE,
                   tool_context=tool_context, root=root)
