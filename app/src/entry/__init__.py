"""Shared bootstrap for all entry points."""

from src.config import settings
from src.db.engine import engine
from src.db.models import Base
from src.db.seed import seed_default_user
from src.log import setup_logging


def init_logging() -> None:
    """Configure logging. Safe to call multiple times."""
    setup_logging(settings.log_level)


async def init_db() -> None:
    """Create tables and seed defaults. Safe to call multiple times."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_default_user()
