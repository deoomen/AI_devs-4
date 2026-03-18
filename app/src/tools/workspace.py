import contextvars
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from src.config import get_workspace_path

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


WORKSPACE_ACL: dict[str, DirAcl] = {
    "inbox":  DirAcl(owner=frozenset({FileOp.READ}),              parent=frozenset({FileOp.WRITE})),
    "notes":  DirAcl(owner=frozenset({FileOp.READ, FileOp.WRITE}), parent=frozenset()),
    "outbox": DirAcl(owner=frozenset({FileOp.READ, FileOp.WRITE}), parent=frozenset({FileOp.READ})),
}


def set_workspace_root(path: Path) -> None:
    """Set the workspace root for the current async context (per-agent)."""
    _workspace_root.set(path)


def get_workspace_root() -> Path:
    """Return the current workspace root (agent-scoped or global fallback)."""
    return _workspace_root.get() or get_workspace_path()


def safe_resolve(relative: str, op: FileOp = FileOp.READ) -> Path | None:
    """Resolve a relative path safely within the current workspace root.

    When agent-scoped (contextvar set), enforces directory restrictions
    based on WORKSPACE_ACL owner permissions:
        write  -> notes/, outbox/ only
        read   -> inbox/, notes/, outbox/ only (+ agent root for listing)

    Returns the resolved Path, or None if access is denied.
    """
    root = get_workspace_root().resolve()
    resolved = (root / relative).resolve()

    # Block escape from workspace boundary
    if not str(resolved).startswith(str(root)):
        return None

    # When agent-scoped, enforce subdirectory access control
    if _workspace_root.get() is not None and resolved != root:
        try:
            top_dir = resolved.relative_to(root).parts[0]
        except (ValueError, IndexError):
            return None
        allowed = {d for d, acl in WORKSPACE_ACL.items() if op in acl.owner}
        if top_dir not in allowed:
            return None

    return resolved
