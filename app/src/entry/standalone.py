"""Standalone agent runtime — no HTTP server needed.

Not meant to be run directly — use `python main.py run` or import StandaloneAgent.
"""

import uuid
from dataclasses import dataclass
from pathlib import Path

from src.config import settings
from src.db.engine import async_session_factory
from src.domain.agent import Agent, WaitEntry
from src.domain.item import Item
from src.domain.session import Session
from src.domain.types import AgentStatus, ItemType
from src.events.emitter import EventEmitter
from src.events.logger import log_event
from src.providers.openrouter import OpenRouterProvider
from src.repositories import create_repositories
from src.runtime.context import RuntimeContext
from src.runtime.runner import deliver_result, run_agent
from src.tools.registry import ToolRegistry
from src.workspace.loader import load_agent_config
from src.workspace.session import SessionWorkspace


def _extract_last_assistant_text(items: list[Item]) -> str | None:
    for item in reversed(items):
        if item.type == ItemType.MESSAGE and item.role == "assistant" and item.content:
            return item.content
    return None


@dataclass
class AgentResult:
    agent_id: str
    status: AgentStatus
    output: str | None
    waiting_for: list[WaitEntry] | None = None


class StandaloneAgent:
    """Stateful wrapper for running an agent across multiple turns without HTTP."""

    def __init__(self, agent_name: str):
        self._agent_name = agent_name
        self._agent_id: str | None = None
        self._tools = ToolRegistry.build_default()
        self._provider = OpenRouterProvider()
        self._events = EventEmitter()
        self._events.on("*", log_event)

    async def send(self, message: str) -> AgentResult:
        async with async_session_factory() as db:
            repos = create_repositories(db)
            ctx = RuntimeContext(
                repos=repos, provider=self._provider,
                tools=self._tools, events=self._events,
            )

            if self._agent_id is None:
                result = await self._create_and_run(ctx, message)
            else:
                result = await self._continue(ctx, message)

            await db.commit()
        return result

    async def deliver(self, call_id: str, output: str) -> AgentResult:
        """Deliver an answer to a waiting agent (e.g. ask_user response)."""
        if self._agent_id is None:
            raise ValueError("No agent to deliver to")

        async with async_session_factory() as db:
            repos = create_repositories(db)
            ctx = RuntimeContext(
                repos=repos, provider=self._provider,
                tools=self._tools, events=self._events,
            )

            agent = await repos.agents.get(self._agent_id)
            if agent is None:
                raise ValueError(f"Agent '{self._agent_id}' not found in DB")
            if agent.status != AgentStatus.WAITING:
                raise ValueError(f"Agent is not waiting (status={agent.status})")

            if agent.workspace_path:
                ctx.agent_workspace = Path(agent.workspace_path)

            agent = await deliver_result(ctx, agent, call_id, output)
            items = await repos.items.list_by_agent(agent.id)
            await db.commit()

        return AgentResult(
            agent_id=agent.id,
            status=agent.status,
            output=_extract_last_assistant_text(items),
            waiting_for=agent.waiting_for if agent.waiting_for else None,
        )

    async def _create_and_run(self, ctx: RuntimeContext, message: str) -> AgentResult:
        agent_config = load_agent_config(self._agent_name)
        if agent_config is None:
            raise ValueError(f"Agent '{self._agent_name}' not found")
        if not agent_config.model:
            agent_config.model = settings.openrouter_default_model

        session = Session(id=str(uuid.uuid4()), user_id="standalone")
        await ctx.repos.sessions.create(session)

        ws = SessionWorkspace(session.id)
        ws.setup()

        agent_id = str(uuid.uuid4())
        agent_ws = ws.create_agent_dir(agent_id)
        agent = Agent(
            id=agent_id,
            session_id=session.id,
            status=AgentStatus.PENDING,
            config=agent_config,
            workspace_path=str(agent_ws),
        )
        await ctx.repos.agents.create(agent)
        self._agent_id = agent.id
        ctx.agent_workspace = agent_ws

        await self._add_user_message(ctx, agent.id, message)
        return await self._run_and_collect(ctx, agent)

    async def _continue(self, ctx: RuntimeContext, message: str) -> AgentResult:
        agent = await ctx.repos.agents.get(self._agent_id)
        if agent is None:
            raise ValueError(f"Agent '{self._agent_id}' not found in DB")

        if agent.workspace_path:
            ctx.agent_workspace = Path(agent.workspace_path)

        agent.status = AgentStatus.PENDING
        agent.turn_count = 0
        await ctx.repos.agents.update(agent)

        await self._add_user_message(ctx, agent.id, message)
        return await self._run_and_collect(ctx, agent)

    async def _add_user_message(self, ctx: RuntimeContext, agent_id: str, message: str) -> None:
        seq = await ctx.repos.items.next_sequence(agent_id)
        item = Item(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            sequence=seq,
            type=ItemType.MESSAGE,
            role="user",
            content=message,
        )
        await ctx.repos.items.create(item)

    async def _run_and_collect(self, ctx: RuntimeContext, agent: Agent) -> AgentResult:
        agent = await run_agent(ctx, agent)
        items = await ctx.repos.items.list_by_agent(agent.id)
        return AgentResult(
            agent_id=agent.id,
            status=agent.status,
            output=_extract_last_assistant_text(items),
            waiting_for=agent.waiting_for if agent.waiting_for else None,
        )
