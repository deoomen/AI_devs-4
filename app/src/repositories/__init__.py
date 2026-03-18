from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from .agent import AgentRepository
from .entry import EntryRepository
from .session import SessionRepository
from .user import UserRepository


@dataclass
class Repositories:
    users: UserRepository
    sessions: SessionRepository
    agents: AgentRepository
    entries: EntryRepository


def create_repositories(db: AsyncSession) -> Repositories:
    return Repositories(
        users=UserRepository(db),
        sessions=SessionRepository(db),
        agents=AgentRepository(db),
        entries=EntryRepository(db),
    )
