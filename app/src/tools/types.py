from dataclasses import dataclass
from typing import Callable, Awaitable

from src.domain.types import ToolType


@dataclass
class ToolDefinition:
    """OpenAI-compatible function tool definition."""
    name: str
    description: str
    parameters: dict


@dataclass
class ToolResult:
    output: str
    is_error: bool = False


@dataclass
class Tool:
    name: str
    type: ToolType
    definition: ToolDefinition
    execute: Callable[..., Awaitable[ToolResult]] | None = None
