import re

from loguru import logger

from src.domain.types import ToolType
from ..types import Tool, ToolDefinition, ToolResult
from ..workspace import FileOp, safe_resolve


async def _execute(arguments: dict) -> ToolResult:
    path = arguments.get("path", "")
    pattern = arguments.get("pattern", "")

    if not path:
        return ToolResult(output="Missing path", is_error=True)
    if not pattern:
        return ToolResult(output="Missing pattern", is_error=True)

    safe = safe_resolve(path, FileOp.READ)
    if safe is None:
        return ToolResult(output=f"Read denied: {path}", is_error=True)
    if not safe.exists() or not safe.is_file():
        return ToolResult(output=f"File not found: {path}", is_error=True)

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return ToolResult(output=f"Invalid regex: {e}", is_error=True)

    lines = safe.read_text(encoding="utf-8").splitlines()
    matches = [f"{i + 1}: {line}" for i, line in enumerate(lines) if regex.search(line)]

    logger.debug("grep_file {} pattern='{}': {} matches out of {} lines", path, pattern, len(matches), len(lines))
    header = f"[{len(matches)} matches in {len(lines)} lines]"
    return ToolResult(output=f"{header}\n" + "\n".join(matches) if matches else f"{header}\nNo matches found.")


grep_file_tool = Tool(
    name="grep_file",
    type=ToolType.SYNC,
    definition=ToolDefinition(
        name="grep_file",
        description=(
            "Search inside a file using a regex pattern. "
            "Returns matching lines with line numbers. Case-insensitive."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to workspace",
                },
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to match against each line (e.g. 'INFO|WARN|ERRO|CRIT')",
                },
            },
            "required": ["path", "pattern"],
        },
    ),
    execute=_execute,
)
