"""Tracing abstraction layer.

Exposes a provider-agnostic interface for agent tracing.
Currently backed by Langfuse — swap the provider import to change backend.
"""

from loguru import logger

from src.config import settings
from src.events.emitter import EventEmitter


def is_tracing_enabled() -> bool:
    return bool(settings.langfuse_public_key and settings.langfuse_secret_key)


def shutdown_tracing() -> None:
    """Flush pending events to the tracing provider (call on app shutdown)."""
    if not is_tracing_enabled():
        return
    from src.tracing.langfuse import get_client  # noqa: PLC0415

    client = get_client()
    if client is not None:
        client.flush()


def subscribe_tracing(events: EventEmitter) -> None:
    """Attach tracing listeners to the event emitter. No-op when tracing is off."""
    if not is_tracing_enabled():
        return
    from src.tracing.langfuse import attach_listeners, get_client  # noqa: PLC0415

    client = get_client()
    if client is None:
        return
    attach_listeners(client, events)
    logger.info("Tracing subscriber attached")
