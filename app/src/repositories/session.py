from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import SessionRow
from src.domain.session import Session


class SessionRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(self, session: Session) -> Session:
        row = SessionRow(id=session.id, user_id=session.user_id, status=session.status)
        self._db.add(row)
        await self._db.flush()
        return session

    async def get(self, session_id: str) -> Session | None:
        result = await self._db.execute(
            select(SessionRow).where(SessionRow.id == session_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return Session(id=row.id, user_id=row.user_id, status=row.status)
