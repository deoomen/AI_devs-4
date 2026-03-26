import hashlib

from sqlalchemy import select

from src.config import settings
from src.db.engine import async_session_factory
from src.db.models import UserRow
from src.domain.ids import UserId

SERVER_USER_ID = UserId("bb2932d8-f146-4500-a932-d8f146c500c8")
STANDALONE_USER_ID = UserId("bc47a89c-d1de-4828-87a8-9cd1de582859")

async def seed_default_user() -> None:
    async with async_session_factory() as session:
        api_key_hash = hashlib.sha256(settings.api_key.encode()).hexdigest()
        result = await session.execute(
            select(UserRow).where(UserRow.api_key_hash == api_key_hash)
        )
        if result.scalars() is None:
            session.add(
                UserRow(
                    id=SERVER_USER_ID,
                    email="server@agent.local",
                    api_key_hash=api_key_hash,
                )
            )
            session.add(
                UserRow(
                    id=STANDALONE_USER_ID,
                    email="standalone@agent.local",
                    api_key_hash=api_key_hash,
                )
            )
            await session.commit()
