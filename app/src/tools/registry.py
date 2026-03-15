import logging

from src.domain.types import ToolType
from .types import Tool, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool
        logger.info("Registered tool: %s (type=%s)", tool.name, tool.type)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def get_definitions(self, names: list[str] | None = None) -> list[dict]:
        """Return OpenAI-compatible tool definitions."""
        tools = self._tools.values() if names is None else [
            self._tools[n] for n in names if n in self._tools
        ]
        return [
            {
                "type": "function",
                "function": {
                    "name": t.definition.name,
                    "description": t.definition.description,
                    "parameters": t.definition.parameters,
                },
            }
            for t in tools
        ]

    async def execute(self, name: str, arguments: dict) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(output=f"Unknown tool: {name}", is_error=True)
        if tool.type == ToolType.HUMAN:
            # HUMAN tools don't execute — they pause the agent
            return ToolResult(output="", is_error=False)
        if tool.execute is None:
            return ToolResult(output=f"Tool {name} has no executor", is_error=True)
        return await tool.execute(arguments)
