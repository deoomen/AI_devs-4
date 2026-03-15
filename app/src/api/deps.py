from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.db.engine import async_session_factory
from src.domain.user import User
from src.events.emitter import EventEmitter
from src.events.logger import log_event
from src.middleware.auth import authenticate
from src.middleware.rate_limit import rate_limiter
from src.providers.openrouter import OpenRouterProvider
from src.repositories import create_repositories
from src.runtime.context import RuntimeContext
from src.tools.ask_user import ask_user_tool
from src.tools.registry import ToolRegistry

_bearer_scheme = HTTPBearer()
_provider = OpenRouterProvider()


def _build_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ask_user_tool)
    return registry


_tool_registry = _build_tool_registry()


def _build_event_emitter() -> EventEmitter:
    emitter = EventEmitter()
    emitter.on("*", log_event)
    return emitter


_event_emitter = _build_event_emitter()


async def get_runtime() -> RuntimeContext:
    async with async_session_factory() as db:
        repos = create_repositories(db)
        ctx = RuntimeContext(
            repos=repos,
            provider=_provider,
            tools=_tool_registry,
            events=_event_emitter,
        )
        yield ctx
        await db.commit()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
) -> User:
    async with async_session_factory() as db:
        repos = create_repositories(db)
        user = await authenticate(f"Bearer {credentials.credentials}", repos.users)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return user


async def check_rate_limit(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not rate_limiter.check(user.id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    return user
