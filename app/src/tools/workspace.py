import contextvars
from pathlib import Path

from src.config import get_workspace_path

_workspace_root: contextvars.ContextVar[Path | None] = contextvars.ContextVar(
    "workspace_root", default=None,
)


def set_workspace_root(path: Path) -> None:
    """Set the workspace root for the current async context (per-agent)."""
    _workspace_root.set(path)


def get_workspace_root() -> Path:
    """Return the current workspace root (agent-scoped or global fallback)."""
    return _workspace_root.get() or get_workspace_path()


def safe_resolve(relative: str) -> Path | None:
    """Resolve a relative path safely within the current workspace root.

    Uses the per-agent workspace root if set, otherwise falls back
    to the global workspace directory.

    Returns the resolved Path, or None if the path escapes the boundary.
    """
    root = get_workspace_root().resolve()
    resolved = (root / relative).resolve()
    if not str(resolved).startswith(str(root)):
        return None
    return resolved
