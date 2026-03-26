import contextvars
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from src.config import get_workspace_path, to_absolute_workspace

_workspace_root: contextvars.ContextVar[Path | None] = contextvars.ContextVar(
    "workspace_root", default=None,
)


class FileOp(str, Enum):
    READ = "read"
    WRITE = "write"


@dataclass(frozen=True)
class DirAcl:
    owner: frozenset[FileOp]
    parent: frozenset[FileOp]


SHARED_DIR = "shared"

WORKSPACE_ACL: dict[str, DirAcl] = {
    "inbox":     DirAcl(owner=frozenset({FileOp.READ}),              parent=frozenset({FileOp.WRITE})),
    "notes":     DirAcl(owner=frozenset({FileOp.READ, FileOp.WRITE}), parent=frozenset()),
    "outbox":    DirAcl(owner=frozenset({FileOp.READ, FileOp.WRITE}), parent=frozenset({FileOp.READ})),
    SHARED_DIR:  DirAcl(owner=frozenset({FileOp.READ}),              parent=frozenset()),
}


def set_workspace_root(relative: Path) -> None:
    """Set the workspace root for the current async context (per-agent).

    Accepts a workspace-relative path, resolves to absolute internally.
    """
    _workspace_root.set(to_absolute_workspace(relative))


def get_workspace_root() -> Path:
    """Return the current workspace root (agent-scoped or global fallback)."""
    return _workspace_root.get() or get_workspace_path()


def get_shared_path() -> Path:
    """Return the global shared directory (workspace/shared/). Created on first call."""
    shared = get_workspace_path() / SHARED_DIR
    shared.mkdir(parents=True, exist_ok=True)
    return shared


def safe_resolve(relative: str, op: FileOp = FileOp.READ) -> Path | None:
    """Resolve a relative path safely within the current workspace root.

    When agent-scoped (contextvar set), enforces directory restrictions
    based on WORKSPACE_ACL owner permissions:
        write  -> notes/, outbox/ only
        read   -> inbox/, notes/, outbox/, shared/ only (+ agent root for listing)

    The ``shared/`` directory is special: it resolves against the global
    workspace root (persistent across sessions) instead of the agent root.
    Its permissions are governed by WORKSPACE_ACL like every other directory.

    Returns the resolved Path, or None if access is denied.
    """
    root = get_workspace_root().resolve()
    parts = Path(relative).parts
    top_dir = parts[0] if parts else None

    # shared/ resolves against global workspace root, not agent-scoped root
    if top_dir == SHARED_DIR:
        shared_root = get_shared_path().resolve()
        resolved = (shared_root / Path(*parts[1:])).resolve() if len(parts) > 1 else shared_root
        boundary = shared_root
    else:
        resolved = (root / relative).resolve()
        boundary = root

    # Block escape from boundary
    if not str(resolved).startswith(str(boundary)):
        return None

    # When agent-scoped, enforce subdirectory access control via ACL
    if _workspace_root.get() is not None and resolved != root:
        if top_dir is None:
            return None
        allowed = {d for d, acl in WORKSPACE_ACL.items() if op in acl.owner}
        if top_dir not in allowed:
            return None

    return resolved
