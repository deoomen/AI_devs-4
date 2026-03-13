import json
import logging
from collections.abc import Callable
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Tool(BaseModel):
    name: str
    definition: dict


class ToolCalling:
    def __init__(self, max_iterations: int = 5) -> None:
        self._tools: dict[str, tuple[Tool, Callable]] = {}
        self.max_iterations: int = max_iterations

    def register_tool(self, tool: Tool, handler: Callable) -> None:
        self._tools[tool.name] = (tool, handler)

    def get_definitions(self) -> list[dict]:
        return [tool.definition for tool, _ in self._tools.values()]

    async def execute_tool(self, name: str, args: dict) -> str:
        entry = self._tools.get(name)
        if entry is None:
            return f"Unknown tool: {name}"
        _, handler = entry
        result = await handler(**args)
        return json.dumps(result)
