from dataclasses import dataclass, field

from .ids import AgentId, EntryId, SessionId
from .types import EntryType, Role


@dataclass
class Entry:
    id: EntryId
    session_id: SessionId
    agent_id: AgentId
    turn: int
    sequence: int
    type: EntryType
    role: Role
    content: str | None = None
    call_id: str | None = None
    name: str | None = None
    arguments: dict | None = None
    output: str | None = None
    is_error: bool = False
