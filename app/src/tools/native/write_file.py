import logging

from src.domain.types import ToolType
from ..types import Tool, ToolDefinition, ToolResult
from ..workspace import safe_resolve

logger = logging.getLogger(__name__)


async def _execute(arguments: dict) -> ToolResult:
    path = arguments.get("path", "")
    content = arguments.get("content", "")

    if not path:
        return ToolResult(output="Missing path", is_error=True)

    safe = safe_resolve(path)
    if safe is None:
        return ToolResult(output="Path escapes workspace boundary", is_error=True)

    safe.parent.mkdir(parents=True, exist_ok=True)
    safe.write_text(content, encoding="utf-8")
    logger.debug("write_file %s (%d bytes)", path, len(content))
    return ToolResult(output=f"Written {len(content)} bytes to {path}")


write_file_tool = Tool(
    name="write_file",
    type=ToolType.SYNC,
    definition=ToolDefinition(
        name="write_file",
        description="Write content to a file in the agent workspace. Creates parent directories if needed. Overwrites existing files.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to workspace",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write",
                },
            },
            "required": ["path", "content"],
        },
    ),
    execute=_execute,
)
