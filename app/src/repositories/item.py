import json

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ItemRow
from src.domain.item import Item
from src.domain.types import ItemType


def _item_from_row(row: ItemRow) -> Item:
    arguments = json.loads(row.arguments_json) if row.arguments_json else None
    return Item(
        id=row.id,
        agent_id=row.agent_id,
        sequence=row.sequence,
        type=ItemType(row.type),
        role=row.role,
        content=row.content,
        call_id=row.call_id,
        name=row.name,
        arguments=arguments,
        output=row.output,
        is_error=row.is_error,
    )


class ItemRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(self, item: Item) -> Item:
        row = ItemRow(
            id=item.id,
            agent_id=item.agent_id,
            sequence=item.sequence,
            type=item.type.value,
            role=item.role,
            content=item.content,
            call_id=item.call_id,
            name=item.name,
            arguments_json=json.dumps(item.arguments) if item.arguments else None,
            output=item.output,
            is_error=item.is_error,
        )
        self._db.add(row)
        await self._db.flush()
        return item

    async def list_by_agent(self, agent_id: str) -> list[Item]:
        result = await self._db.execute(
            select(ItemRow)
            .where(ItemRow.agent_id == agent_id)
            .order_by(ItemRow.sequence)
        )
        return [_item_from_row(row) for row in result.scalars().all()]

    async def next_sequence(self, agent_id: str) -> int:
        result = await self._db.execute(
            select(func.coalesce(func.max(ItemRow.sequence), -1))
            .where(ItemRow.agent_id == agent_id)
        )
        return result.scalar() + 1
