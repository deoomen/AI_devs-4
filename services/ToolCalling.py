import json
import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


class ToolCalling:
    def __init__(self, max_iterations: int = 5) -> None:
        self._handlers: dict[str, Callable] = {}
        self.max_iterations: int = max_iterations

    def register_tool(self, name: str, handler: Callable) -> None:
        self._handlers[name] = handler

    async def execute_tool(self, name: str, args: dict) -> str:
        handler = self._handlers.get(name)
        if handler is None:
            return f"Unknown tool: {name}"
        result = await handler(**args)
        return json.dumps(result)
