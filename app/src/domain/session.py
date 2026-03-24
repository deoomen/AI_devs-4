from dataclasses import dataclass

from .ids import SessionId, UserId
from .types import SessionStatus


@dataclass
class Session:
    id: SessionId
    user_id: UserId
    status: SessionStatus = SessionStatus.ACTIVE
