from dataclasses import dataclass, field
from .types import EntryType, Role


@dataclass
class Entry:
    id: str
    session_id: str
    agent_id: str
    sequence: int
    type: EntryType
    role: Role
    content: str | None = None
    call_id: str | None = None
    name: str | None = None
    arguments: dict | None = None
    output: str | None = None
    is_error: bool = False
