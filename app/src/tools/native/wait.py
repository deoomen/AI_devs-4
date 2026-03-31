import asyncio

from src.domain.types import ToolType
from ..types import Tool, ToolDefinition, ToolResult


async def _execute(arguments: dict) -> ToolResult:
    seconds = max(1, min(int(arguments.get("seconds", 3)), 30))
    await asyncio.sleep(seconds)
    return ToolResult(output=f"Waited {seconds} second(s).")


wait_tool = Tool(
    name="wait",
    type=ToolType.SYNC,
    parallel_safe=False,
    definition=ToolDefinition(
        name="wait",
        description=(
            "Pause execution for a given number of seconds. "
            "Use when polling for async results that are not ready yet — "
            "call wait, then retry the fetch."
        ),
        parameters={
            "type": "object",
            "properties": {
                "seconds": {
                    "type": "integer",
                    "description": "Seconds to wait (1–30)",
                },
            },
            "required": ["seconds"],
        },
    ),
    execute=_execute,
)
