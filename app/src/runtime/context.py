import contextvars
from dataclasses import dataclass
from pathlib import Path

from src.domain.ids import AgentId, SessionId, UserId
from src.events.emitter import EventEmitter
from src.providers.types import Provider
from src.repositories import Repositories
from src.tools.registry import ToolRegistry

_current_ctx: contextvars.ContextVar["RuntimeContext | None"] = contextvars.ContextVar(
    "runtime_ctx", default=None,
)


@dataclass
class RuntimeContext:
    session_id: SessionId
    repos: Repositories
    provider: Provider
    tools: ToolRegistry
    events: EventEmitter
    user_id: UserId | None = None
    agent_workspace: Path | None = None
    agent_id: AgentId | None = None


def set_runtime_context(ctx: RuntimeContext) -> None:
    _current_ctx.set(ctx)


def get_runtime_context() -> RuntimeContext | None:
    return _current_ctx.get()
