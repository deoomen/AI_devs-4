from loguru import logger

from src.domain.types import ToolType
from ..types import Tool, ToolDefinition, ToolResult
from ..workspace import FileOp, safe_resolve


async def _execute(arguments: dict) -> ToolResult:
    path = arguments.get("path", "")
    if not path:
        return ToolResult(output="Missing path", is_error=True)

    safe = safe_resolve(path, FileOp.READ)
    if safe is None:
        return ToolResult(output=f"Read denied: {path} (use inbox/, notes/, or outbox/)", is_error=True)
    if not safe.exists():
        return ToolResult(output=f"File not found: {path}", is_error=True)
    if not safe.is_file():
        return ToolResult(output=f"Not a file: {path}", is_error=True)

    content = safe.read_text(encoding="utf-8")
    logger.debug("read_file {} ({} bytes)", path, len(content))
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
