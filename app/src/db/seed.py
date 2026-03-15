import hashlib
import uuid

from sqlalchemy import select

from src.config import settings
from src.db.engine import async_session_factory
from src.db.models import UserRow


async def seed_default_user() -> None:
    async with async_session_factory() as session:
        api_key_hash = hashlib.sha256(settings.api_key.encode()).hexdigest()
        result = await session.execute(
            select(UserRow).where(UserRow.api_key_hash == api_key_hash)
        )
        if result.scalar_one_or_none() is None:
            user = UserRow(
                id=str(uuid.uuid4()),
                email="default@agent.local",
                api_key_hash=api_key_hash,
            )
            session.add(user)
            await session.commit()
