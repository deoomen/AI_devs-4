import logging

from .types import Event

logger = logging.getLogger("agent.events")


def log_event(event: Event) -> None:
    logger.info("[%s] agent=%s %s", event.name, event.agent_id[:8], event.data)
