import json
import logging
from collections.abc import Callable
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Tool(BaseModel):
    name: str
    definition: dict
    handle: Callable


class ToolCalling:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register_tool(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get_definitions(self) -> list[dict]:
        return [tool.definition for tool in self._tools.values()]

    async def execute_tool(self, name: str, args: dict) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"Unknown tool: {name}"
        result = await tool.handle(**args)
        return json.dumps(result)
