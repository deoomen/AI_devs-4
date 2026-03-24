import json
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from src.domain.ids import AbstractId, AgentId, EntryId, SessionId, UserId
from src.domain.types import AgentStatus, SessionStatus


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IdColumn(TypeDecorator):
    """Maps domain Id value objects to String(36) in the database."""

    impl = String(36)
    cache_ok = True

    def __init__(self, id_class: type[AbstractId] = AbstractId):
        super().__init__()
        self._id_class = id_class

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return self._id_class(value)


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[UserId] = mapped_column(IdColumn(UserId), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class SessionRow(Base):
    __tablename__ = "sessions"

    id: Mapped[SessionId] = mapped_column(IdColumn(SessionId), primary_key=True)
    user_id: Mapped[UserId] = mapped_column(IdColumn(UserId), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=SessionStatus.ACTIVE.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AgentRow(Base):
    __tablename__ = "agents"

    id: Mapped[AgentId] = mapped_column(IdColumn(AgentId), primary_key=True)
    session_id: Mapped[SessionId] = mapped_column(IdColumn(SessionId), ForeignKey("sessions.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=AgentStatus.PENDING.value)
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    waiting_for_json: Mapped[str] = mapped_column(Text, default="[]")
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    workspace_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_agent_id: Mapped[AgentId | None] = mapped_column(IdColumn(AgentId), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class EntryRow(Base):
    __tablename__ = "entries"

    id: Mapped[EntryId] = mapped_column(IdColumn(EntryId), primary_key=True)
    session_id: Mapped[SessionId] = mapped_column(IdColumn(SessionId), ForeignKey("sessions.id"), nullable=False)
    agent_id: Mapped[AgentId] = mapped_column(IdColumn(AgentId), ForeignKey("agents.id"), nullable=False)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    call_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    arguments_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_error: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
