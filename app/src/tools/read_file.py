import logging
from pathlib import Path

from src.config import get_workspace_path
from src.domain.types import ToolType
from .types import Tool, ToolDefinition, ToolResult

logger = logging.getLogger(__name__)


def _safe_path(relative: str) -> Path | None:
    root = get_workspace_path()
    resolved = (root / relative).resolve()
    if not str(resolved).startswith(str(root)):
        return None
    return resolved


async def _execute(arguments: dict) -> ToolResult:
    path = arguments.get("path", "")
    if not path:
        return ToolResult(output="Missing path", is_error=True)

    safe = _safe_path(path)
    if safe is None:
        return ToolResult(output="Path escapes workspace boundary", is_error=True)
    if not safe.exists():
        return ToolResult(output=f"File not found: {path}", is_error=True)
    if not safe.is_file():
        return ToolResult(output=f"Not a file: {path}", is_error=True)

    content = safe.read_text(encoding="utf-8")
    logger.debug("read_file %s (%d bytes)", path, len(content))
    return ToolResult(output=content)


read_file_tool = Tool(
    name="read_file",
    type=ToolType.SYNC,
    definition=ToolDefinition(
        name="read_file",
        description="Read the contents of a file in the agent workspace.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to workspace",
                },
            },
            "required": ["path"],
        },
    ),
    execute=_execute,
)
