from src.domain.types import ToolType
from ..types import Tool, ToolDefinition, ToolResult


async def _execute(arguments: dict) -> ToolResult:
    thought = arguments.get("thought", "")
    return ToolResult(output=thought)


think_tool = Tool(
    name="think",
    type=ToolType.SYNC,
    definition=ToolDefinition(
        name="think",
        description=(
            "Use this tool to think step-by-step, plan your next actions, "
            "compare data, or reason about a problem before acting. "
            "Your input is returned back to you — no external calls are made. "
            "After reaching important conclusions or a multi-step plan, write them to notes/ with write_file so they persist across turns."
        ),
        parameters={
            "type": "object",
            "properties": {
                "thought": {
                    "type": "string",
                    "description": "Your reasoning, analysis, or plan",
                },
            },
            "required": ["thought"],
        },
    ),
    execute=_execute,
)
