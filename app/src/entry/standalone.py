"""Standalone agent runtime — no HTTP server needed.

Not meant to be run directly — use `python main.py run` or import StandaloneAgent.
"""

from dataclasses import dataclass

from src.config import to_relative_workspace
from src.db.engine import async_session_factory
from src.db.seed import STANDALONE_USER_ID
from src.domain.agent import Agent, WaitEntry
from src.domain.entry import Entry
from src.domain.ids import AgentId, EntryId, SessionId
from src.domain.session import Session
from src.domain.types import AgentStatus, EntryType, Role
from src.events.emitter import EventEmitter
from src.events.logger import log_event
from src.events.types import EventName
from src.providers.openrouter import OpenRouterProvider
from src.repositories import create_repositories
from src.runtime.context import RuntimeContext
from src.runtime.runner import deliver_result, run_agent
from src.tools.registry import ToolRegistry
from src.workspace.loader import load_agent_config
from src.workspace.session import SessionWorkspace
from src.tracing.subscriber import shutdown_tracing, subscribe_tracing


def _extract_last_assistant_text(entries: list[Entry]) -> str | None:
    for entry in reversed(entries):
        if entry.type == EntryType.MESSAGE and entry.role == Role.ASSISTANT and entry.content:
            return entry.content
    return None


@dataclass
class AgentResult:
    agent_id: AgentId
    status: AgentStatus
    output: str | None
    waiting_for: list[WaitEntry] | None = None


class StandaloneAgent:
    """Stateful wrapper for running an agent across multiple turns without HTTP."""

    def __init__(self, agent_name: str):
        self._agent_name = agent_name
        self._session_id = SessionId.generate()
        self._agent_id: AgentId | None = None
        self._session_created = False
        self._tools = ToolRegistry.build_default()
        self._provider = OpenRouterProvider()
        self._events = EventEmitter()
        self._events.on(EventName.ALL, log_event)
        subscribe_tracing(self._events)

    @property
    def session_id(self) -> SessionId:
        return self._session_id

    def _build_ctx(self, repos) -> RuntimeContext:
        return RuntimeContext(
            session_id=self._session_id,
            repos=repos, provider=self._provider,
            tools=self._tools, events=self._events,
            user_id=STANDALONE_USER_ID,
        )

    async def send(self, message: str) -> AgentResult:
        async with async_session_factory() as db:
            repos = create_repositories(db)
            ctx = self._build_ctx(repos)

            if self._agent_id is None:
                result = await self._create_and_run(ctx, message)
            else:
                result = await self._continue(ctx, message)

            await db.commit()
        shutdown_tracing()
        return result

    async def deliver(self, call_id: str, output: str) -> AgentResult:
        """Deliver an answer to a waiting agent (e.g. ask_user response)."""
        if self._agent_id is None:
            raise ValueError("No agent to deliver to")

        async with async_session_factory() as db:
            repos = create_repositories(db)
            ctx = self._build_ctx(repos)

            agent = await repos.agents.get(self._agent_id)
            if agent is None:
                raise ValueError(f"Agent '{self._agent_id}' not found in DB")
            if agent.status != AgentStatus.WAITING:
                raise ValueError(f"Agent is not waiting (status={agent.status})")

            if agent.workspace_path:
                ctx.agent_workspace = agent.workspace_path

            agent = await deliver_result(ctx, agent, call_id, output)
            entries = await repos.entries.list_by_agent(agent.id)
            await db.commit()

        return AgentResult(
            agent_id=agent.id,
            status=agent.status,
            output=_extract_last_assistant_text(entries),
            waiting_for=agent.waiting_for if agent.waiting_for else None,
        )

    async def _ensure_session(self, ctx: RuntimeContext) -> None:
        if not self._session_created:
            session = Session(id=self._session_id, user_id=STANDALONE_USER_ID)
            await ctx.repos.sessions.create(session)
            self._session_created = True

    async def _create_and_run(self, ctx: RuntimeContext, message: str) -> AgentResult:
        agent_config = load_agent_config(self._agent_name)
        if agent_config is None:
            raise ValueError(f"Agent '{self._agent_name}' not found")

        await self._ensure_session(ctx)

        ws = SessionWorkspace(self._session_id)
        ws.setup()

        agent_id = AgentId.generate()
        ws.create_agent_dir(agent_id)
        agent_ws_rel = to_relative_workspace(ws.agent_dir(agent_id))
        agent = Agent(
            id=agent_id,
            session_id=self._session_id,
            status=AgentStatus.PENDING,
            config=agent_config,
            workspace_path=agent_ws_rel,
        )
        await ctx.repos.agents.create(agent)
        self._agent_id = agent.id
        ctx.agent_workspace = agent_ws_rel

        await self._add_user_message(ctx, agent, message)
        return await self._run_and_collect(ctx, agent, user_input=message)

    async def _continue(self, ctx: RuntimeContext, message: str) -> AgentResult:
        agent = await ctx.repos.agents.get(self._agent_id)
        if agent is None:
            raise ValueError(f"Agent '{self._agent_id}' not found in DB")

        if agent.workspace_path:
            ctx.agent_workspace = agent.workspace_path

        agent.status = AgentStatus.PENDING
        agent.turn_count = 0
        await ctx.repos.agents.update(agent)

        await self._add_user_message(ctx, agent, message)
        return await self._run_and_collect(ctx, agent, user_input=message)

    async def _add_user_message(self, ctx: RuntimeContext, agent: Agent, message: str) -> None:
        seq = await ctx.repos.entries.next_sequence(agent.id)
        entry = Entry(
            id=EntryId.generate(),
            session_id=ctx.session_id,
            agent_id=agent.id,
            turn=agent.turn_count,
            sequence=seq,
            type=EntryType.MESSAGE,
            role=Role.USER,
            content=message,
        )
        await ctx.repos.entries.create(entry)

    async def _run_and_collect(self, ctx: RuntimeContext, agent: Agent, user_input: str = "") -> AgentResult:
        agent = await run_agent(ctx, agent, user_input=user_input)
        entries = await ctx.repos.entries.list_by_agent(agent.id)
        return AgentResult(
            agent_id=agent.id,
            status=agent.status,
            output=_extract_last_assistant_text(entries),
            waiting_for=agent.waiting_for if agent.waiting_for else None,
        )
