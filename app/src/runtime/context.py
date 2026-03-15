from dataclasses import dataclass

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
