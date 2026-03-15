from pathlib import Path

from src.config import get_workspace_path


def safe_resolve(relative: str) -> Path | None:
    """Resolve a relative path safely within the agent workspace.

    Returns the resolved Path, or None if the path escapes the workspace boundary.
    """
    root = get_workspace_path()
    resolved = (root / relative).resolve()
    if not str(resolved).startswith(str(root)):
        return None
    return resolved
