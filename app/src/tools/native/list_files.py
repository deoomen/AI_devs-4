import logging

from src.domain.types import ToolType
from ..types import Tool, ToolDefinition, ToolResult
from ..workspace import safe_resolve

logger = logging.getLogger(__name__)


async def _execute(arguments: dict) -> ToolResult:
    path = arguments.get("path", ".")
    safe = safe_resolve(path)
    if safe is None:
        return ToolResult(output="Path escapes workspace boundary", is_error=True)
    if not safe.exists():
        return ToolResult(output=f"Directory not found: {path}", is_error=True)
    if not safe.is_dir():
        return ToolResult(output=f"Not a directory: {path}", is_error=True)

    entries = sorted(safe.iterdir())
    lines = []
    for entry in entries:
        prefix = "d" if entry.is_dir() else "f"
        lines.append(f"{prefix} {entry.name}")

    logger.debug("list_files %s (%d entries)", path, len(lines))
    return ToolResult(output="\n".join(lines) if lines else "(empty)")


list_files_tool = Tool(
    name="list_files",
    type=ToolType.SYNC,
    definition=ToolDefinition(
        name="list_files",
        description="List files and directories in the agent workspace. Returns entries prefixed with 'd' (directory) or 'f' (file).",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path relative to workspace (default: workspace root)",
                    "default": ".",
                },
            },
        },
    ),
    execute=_execute,
)
