import contextvars
from enum import Enum
from pathlib import Path

from src.config import get_workspace_path

_workspace_root: contextvars.ContextVar[Path | None] = contextvars.ContextVar(
    "workspace_root", default=None,
)

_WRITABLE_DIRS = ("notes", "outbox")
_READABLE_DIRS = ("inbox", "notes", "outbox")


class FileOp(str, Enum):
    READ = "read"
    WRITE = "write"


def set_workspace_root(path: Path) -> None:
    """Set the workspace root for the current async context (per-agent)."""
    _workspace_root.set(path)


def get_workspace_root() -> Path:
    """Return the current workspace root (agent-scoped or global fallback)."""
    return _workspace_root.get() or get_workspace_path()


def safe_resolve(relative: str, op: FileOp = FileOp.READ) -> Path | None:
    """Resolve a relative path safely within the current workspace root.

    When agent-scoped (contextvar set), enforces directory restrictions:
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
        allowed = _WRITABLE_DIRS if op == FileOp.WRITE else _READABLE_DIRS
        if top_dir not in allowed:
            return None

    return resolved
