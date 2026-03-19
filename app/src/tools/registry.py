from loguru import logger

from src.domain.types import ToolType
from .types import Tool, ToolResult


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    @classmethod
    def build_default(cls) -> "ToolRegistry":
        """Create a registry with all built-in tools."""
        from .native.aidevs_headquarters import aidevs_headquarters_tool
        from .native.analyze_image import analyze_image_tool
        from .native.ask_user import ask_user_tool
        from .native.count_tokens import count_tokens_tool
        from .native.csv_filter import csv_filter_tool
        from .native.download_file import download_file_tool
        from .native.http_request import http_request_tool
        from .native.list_files import list_files_tool
        from .native.read_file import read_file_tool
        from .native.grep_file import grep_file_tool
        from .native.spawn_agent import spawn_agent_tool
        from .native.think import think_tool
        from .native.write_file import write_file_tool
        from .native.zmail import zmail_tool

        registry = cls()
        registry.register(aidevs_headquarters_tool)
        registry.register(analyze_image_tool)
        registry.register(ask_user_tool)
        registry.register(count_tokens_tool)
        registry.register(csv_filter_tool)
        registry.register(download_file_tool)
        registry.register(http_request_tool)
        registry.register(list_files_tool)
        registry.register(read_file_tool)
        registry.register(grep_file_tool)
        registry.register(spawn_agent_tool)
        registry.register(think_tool)
        registry.register(write_file_tool)
        registry.register(zmail_tool)
        logger.info("Registered built-in tools: {}", len(registry._tools.keys()))

        return registry

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool
        logger.info("Registered tool: {} (type={})", tool.name, tool.type)

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
        from .template import resolve_args

        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(output=f"Unknown tool: {name}", is_error=True)
        if tool.type == ToolType.HUMAN:
            # HUMAN tools don't execute — they pause the agent
            return ToolResult(output="", is_error=False)
        if tool.execute is None:
            return ToolResult(output=f"Tool {name} has no executor", is_error=True)
        resolved = resolve_args(arguments)
        return await tool.execute(resolved)
