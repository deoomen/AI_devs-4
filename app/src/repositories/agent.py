import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AgentRow
from src.domain.agent import Agent, AgentConfig, WaitEntry
from src.domain.types import AgentStatus, WaitType


def _agent_from_row(row: AgentRow) -> Agent:
    config_data = json.loads(row.config_json)
    config = AgentConfig(**config_data)
    waiting = [
        WaitEntry(
            call_id=w["call_id"],
            tool_name=w["tool_name"],
            type=WaitType(w.get("type", "tool_result")),
        )
        for w in json.loads(row.waiting_for_json)
    ]
    return Agent(
        id=row.id,
        session_id=row.session_id,
        status=AgentStatus(row.status),
        config=config,
        turn_count=row.turn_count,
        waiting_for=waiting,
        workspace_path=row.workspace_path,
    )


def _agent_to_row_data(agent: Agent) -> dict:
    config_data = {
        "name": agent.config.name,
        "model": agent.config.model,
        "system_prompt": agent.config.system_prompt,
        "tools": agent.config.tools,
        "max_turns": agent.config.max_turns,
    }
    waiting_data = [
        {"call_id": w.call_id, "tool_name": w.tool_name, "type": w.type.value}
        for w in agent.waiting_for
    ]
    return {
        "status": agent.status.value,
        "config_json": json.dumps(config_data),
        "waiting_for_json": json.dumps(waiting_data),
        "turn_count": agent.turn_count,
        "workspace_path": agent.workspace_path,
    }


class AgentRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(self, agent: Agent) -> Agent:
        data = _agent_to_row_data(agent)
        row = AgentRow(id=agent.id, session_id=agent.session_id, **data)
        self._db.add(row)
        await self._db.flush()
        return agent

    async def get(self, agent_id: str) -> Agent | None:
        result = await self._db.execute(
            select(AgentRow).where(AgentRow.id == agent_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return _agent_from_row(row)

    async def update(self, agent: Agent) -> Agent:
        result = await self._db.execute(
            select(AgentRow).where(AgentRow.id == agent.id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise ValueError(f"Agent {agent.id} not found")
        data = _agent_to_row_data(agent)
        for key, value in data.items():
            setattr(row, key, value)
        await self._db.flush()
        return agent
