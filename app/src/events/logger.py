from loguru import logger

from .types import Event


def log_event(event: Event) -> None:
    logger.info("[{}] agent={} {}", event.name, event.agent_id[:8], event.data)
