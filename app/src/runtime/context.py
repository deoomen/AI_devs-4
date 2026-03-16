from dataclasses import dataclass, field
from pathlib import Path

from src.events.emitter import EventEmitter
from src.providers.types import Provider
from src.repositories import Repositories
from src.tools.registry import ToolRegistry


@dataclass
class RuntimeContext:
    repos: Repositories
    provider: Provider
    tools: ToolRegistry
    events: EventEmitter
    agent_workspace: Path | None = None
