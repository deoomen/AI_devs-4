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
        return ToolResult(output=f"Read denied: {path} (use inbox/, notes/, outbox/, or shared/)", is_error=True)
    if not safe.exists():
        return ToolResult(output=f"File not found: {path}", is_error=True)
    if not safe.is_file():
        return ToolResult(output=f"Not a file: {path}", is_error=True)

    lines = safe.read_text(encoding="utf-8").splitlines(keepends=True)
    total_lines = len(lines)

    offset = arguments.get("offset", 0)
    limit = arguments.get("limit", 0)

    if offset > 0:
        lines = lines[offset:]
    if limit > 0:
        lines = lines[:limit]

    content = "".join(lines)
    read_count = len(lines)

    meta = f"[lines {offset + 1}-{offset + read_count} of {total_lines}]"
    logger.debug("read_file {} {} ({} bytes)", path, meta, len(content))
    return ToolResult(output=f"{meta}\n{content}")


read_file_tool = Tool(
    name="read_file",
    type=ToolType.SYNC,
    definition=ToolDefinition(
        name="read_file",
        description=(
            "Read the contents of a file in the agent workspace. "
            "Supports optional offset/limit for chunked reading of large files. "
            "Returns a header line with line range info followed by the content. "
            "Readable directories: inbox/ (files from parent/sub-agents), notes/ (your scratchpad), outbox/ (your results), shared/ (persistent cross-run cache)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to workspace (e.g. inbox/agnt_abc/result.md, notes/plan.md, shared/cached_data.json)",
                },
                "offset": {
                    "type": "integer",
                    "description": "Number of lines to skip from the start (0-based, default 0)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of lines to return (0 = all remaining, default 0)",
                },
            },
            "required": ["path"],
        },
    ),
    execute=_execute,
)
