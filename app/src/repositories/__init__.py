from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from .agent import AgentRepository
from .item import ItemRepository
from .session import SessionRepository
from .user import UserRepository


@dataclass
class Repositories:
    users: UserRepository
    sessions: SessionRepository
    agents: AgentRepository
    items: ItemRepository


def create_repositories(db: AsyncSession) -> Repositories:
    return Repositories(
        users=UserRepository(db),
        sessions=SessionRepository(db),
        agents=AgentRepository(db),
        items=ItemRepository(db),
    )
