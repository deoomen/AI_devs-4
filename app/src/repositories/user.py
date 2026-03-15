from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import UserRow
from src.domain.user import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_by_api_key_hash(self, key_hash: str) -> User | None:
        result = await self._db.execute(
            select(UserRow).where(UserRow.api_key_hash == key_hash)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return User(id=row.id, email=row.email, api_key_hash=row.api_key_hash)
