import logging

from src.domain.types import ToolType
from .types import Tool, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    @classmethod
    def build_default(cls) -> "ToolRegistry":
        """Create a registry with all built-in tools."""
        from .native.aidevs_headquarters import aidevs_headquarters_tool
        from .native.ask_user import ask_user_tool
        from .native.csv_filter import csv_filter_tool
        from .native.http_request import http_request_tool
        from .native.list_files import list_files_tool
        from .native.read_file import read_file_tool
        from .native.write_file import write_file_tool

        registry = cls()
        registry.register(aidevs_headquarters_tool)
        registry.register(ask_user_tool)
        registry.register(csv_filter_tool)
        registry.register(http_request_tool)
        registry.register(list_files_tool)
        registry.register(read_file_tool)
        registry.register(write_file_tool)
        return registry

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
