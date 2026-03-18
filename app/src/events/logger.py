from loguru import logger

from .types import Event, EventName

# Events with large payloads (full message history) — skip verbose logging
_QUIET_EVENTS = {EventName.GENERATION_STARTED, EventName.GENERATION_COMPLETED}


def log_event(event: Event) -> None:
    if event.name in _QUIET_EVENTS:
        return
    logger.debug("[{}] {}", event.name, event.data)
