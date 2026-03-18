from loguru import logger

from src.domain.types import ToolType
from src.utils.tokens import estimate_tokens
from ..types import Tool, ToolDefinition, ToolResult
from ..workspace import FileOp, safe_resolve


async def _execute(arguments: dict) -> ToolResult:
    text = arguments.get("text")
    path = arguments.get("path")

    if not text and not path:
        return ToolResult(output="Provide either 'text' or 'path'", is_error=True)

    if path:
        safe = safe_resolve(path, FileOp.READ)
        if safe is None:
            return ToolResult(output=f"Read denied: {path}", is_error=True)
        if not safe.exists() or not safe.is_file():
            return ToolResult(output=f"File not found: {path}", is_error=True)
        text = safe.read_text(encoding="utf-8")

    tokens = estimate_tokens(text)
    lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)

    logger.debug("count_tokens: {} chars, ~{} tokens, {} lines", len(text), tokens, lines)
    return ToolResult(output=f"~{tokens} tokens ({len(text)} chars, {lines} lines)")


count_tokens_tool = Tool(
    name="count_tokens",
    type=ToolType.SYNC,
    definition=ToolDefinition(
        name="count_tokens",
        description=(
            "Estimate the token count of a text string or a file in the workspace. "
            "Uses a conservative estimate that may slightly overcount. "
            "Provide either 'text' directly or 'path' to read from a file."
        ),
        parameters={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to count tokens for",
                },
                "path": {
                    "type": "string",
                    "description": "File path relative to workspace (alternative to text)",
                },
            },
        },
    ),
    execute=_execute,
)
