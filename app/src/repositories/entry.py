import json

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import EntryRow
from src.domain.entry import Entry
from src.domain.types import EntryType


def _entry_from_row(row: EntryRow) -> Entry:
    arguments = json.loads(row.arguments_json) if row.arguments_json else None
    return Entry(
        id=row.id,
        agent_id=row.agent_id,
        sequence=row.sequence,
        type=EntryType(row.type),
        role=row.role,
        content=row.content,
        call_id=row.call_id,
        name=row.name,
        arguments=arguments,
        output=row.output,
        is_error=row.is_error,
    )


class EntryRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(self, entry: Entry) -> Entry:
        row = EntryRow(
            id=entry.id,
            agent_id=entry.agent_id,
            sequence=entry.sequence,
            type=entry.type.value,
            role=entry.role,
            content=entry.content,
            call_id=entry.call_id,
            name=entry.name,
            arguments_json=json.dumps(entry.arguments) if entry.arguments else None,
            output=entry.output,
            is_error=entry.is_error,
        )
        self._db.add(row)
        await self._db.flush()
        return entry

    async def list_by_agent(self, agent_id: str) -> list[Entry]:
        result = await self._db.execute(
            select(EntryRow)
            .where(EntryRow.agent_id == agent_id)
            .order_by(EntryRow.sequence)
        )
        return [_entry_from_row(row) for row in result.scalars().all()]

    async def next_sequence(self, agent_id: str) -> int:
        result = await self._db.execute(
            select(func.coalesce(func.max(EntryRow.sequence), -1))
            .where(EntryRow.agent_id == agent_id)
        )
        return result.scalar() + 1
