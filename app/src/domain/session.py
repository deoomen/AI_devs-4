from dataclasses import dataclass

from .types import SessionStatus


@dataclass
class Session:
    id: str
    user_id: str
    status: SessionStatus = SessionStatus.ACTIVE
