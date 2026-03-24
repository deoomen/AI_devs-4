import uuid
from typing import Self


class AbstractId(uuid.UUID):
    """Base value object for all domain identifiers.

    Extends uuid.UUID — inherits equality, hashing, and string formatting.
    """

    @classmethod
    def generate(cls) -> Self:
        return cls(str(uuid.uuid4()))

    def short(self) -> str:
        """First 8 hex characters (no dashes). Safe for paths and logs."""
        return self.hex[:8]


class UserId(AbstractId):
    pass


class SessionId(AbstractId):
    pass


class AgentId(AbstractId):
    pass


class EntryId(AbstractId):
    pass
