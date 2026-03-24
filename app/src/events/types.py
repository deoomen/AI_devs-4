from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum

from src.domain.ids import AgentId


class EventName(StrEnum):
    ALL = "*"
    AGENT_STARTED = "agent.started"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"
    AGENT_WAITING = "agent.waiting"
    AGENT_RESUMED = "agent.resumed"
    TURN_START = "turn.start"
    GENERATION_STARTED = "generation.started"
    GENERATION_COMPLETED = "generation.completed"
    TOOL_STARTED = "tool.started"
    TOOL_HUMAN_REQUESTED = "tool.human_requested"
    TOOL_COMPLETED = "tool.completed"


@dataclass
class Event:
    name: EventName
    agent_id: AgentId
    data: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
