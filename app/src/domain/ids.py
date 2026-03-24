import uuid
from typing import Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema


class AbstractId(uuid.UUID):
    """Base value object for all domain identifiers.

    Extends uuid.UUID — inherits equality, hashing, and string formatting.
    Pydantic-aware: FastAPI auto-converts path/query params and request bodies.
    """

    @classmethod
    def generate(cls) -> Self:
        return cls(str(uuid.uuid4()))

    def short(self) -> str:
        """First 8 hex characters (no dashes). Safe for paths and logs."""
        return self.hex[:8]

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler: GetCoreSchemaHandler):
        return core_schema.no_info_plain_validator_function(
            cls._pydantic_validate,
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def _pydantic_validate(cls, value):
        if isinstance(value, cls):
            return value
        if isinstance(value, (uuid.UUID, str)):
            return cls(str(value))
        raise ValueError(f"Cannot convert {type(value).__name__} to {cls.__name__}")


class UserId(AbstractId):
    pass


class SessionId(AbstractId):
    pass


class AgentId(AbstractId):
    pass


class EntryId(AbstractId):
    pass
