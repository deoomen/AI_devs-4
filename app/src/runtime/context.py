import contextvars
from dataclasses import dataclass
from pathlib import Path

from src.events.emitter import EventEmitter
from src.providers.types import Provider
from src.repositories import Repositories
from src.tools.registry import ToolRegistry

_current_ctx: contextvars.ContextVar["RuntimeContext | None"] = contextvars.ContextVar(
    "runtime_ctx", default=None,
)


@dataclass
class RuntimeContext:
    session_id: str
    repos: Repositories
    provider: Provider
    tools: ToolRegistry
    events: EventEmitter
    agent_workspace: Path | None = None
    agent_id: str | None = None


def set_runtime_context(ctx: RuntimeContext) -> None:
    _current_ctx.set(ctx)


def get_runtime_context() -> RuntimeContext | None:
    return _current_ctx.get()
