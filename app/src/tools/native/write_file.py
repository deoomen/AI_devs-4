from loguru import logger

from src.domain.types import ToolType
from ..types import Tool, ToolDefinition, ToolResult
from ..workspace import FileOp, safe_resolve


async def _execute(arguments: dict) -> ToolResult:
    path = arguments.get("path", "")
    content = arguments.get("content", "")
    append = arguments.get("append", False)

    if not path:
        return ToolResult(output="Missing path", is_error=True)

    safe = safe_resolve(path, FileOp.WRITE)
    if safe is None:
        return ToolResult(output=f"Write denied: {path} (use notes/ or outbox/)", is_error=True)

    safe.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with safe.open(mode, encoding="utf-8") as f:
        f.write(content)
    action = "Appended" if append else "Written"
    logger.debug("write_file {} ({} bytes, mode={})", path, len(content), mode)
    return ToolResult(output=f"{action} {len(content)} bytes to {path}")


write_file_tool = Tool(
    name="write_file",
    type=ToolType.SYNC,
    definition=ToolDefinition(
        name="write_file",
        description=(
            "Write content to a file in the agent workspace. Creates parent directories if needed. "
            "Overwrites existing files by default; set append=true to add to the end of an existing file. "
            "Directory guide: "
            "notes/ — ephemeral scratchpad for this run: plans, API responses, raw data, reasoning checkpoints; "
            "outbox/ — final results for the parent agent to read; "
            "shared/ — persistent global cache across ALL runs and agents: use for expensive fetched data, API docs, or anything worth reusing next time. "
            "Prefer writing to files over keeping large data in conversation context."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to workspace (e.g. notes/plan.md, outbox/result.md, shared/api_docs.md)",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write",
                },
                "append": {
                    "type": "boolean",
                    "description": "If true, append content to the end of the file instead of overwriting. Defaults to false.",
                },
            },
            "required": ["path", "content"],
        },
    ),
    execute=_execute,
)
