from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Event:
    name: str
    agent_id: str
    data: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
