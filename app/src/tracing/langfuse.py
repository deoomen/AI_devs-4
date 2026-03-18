"""Langfuse client management.

Initializes the singleton Langfuse client and exposes flush() for shutdown.
Tracing is disabled (no-op) when LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY
are not set or the `langfuse` package is not installed.

Actual observation logic lives in `subscriber.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from src.config import settings

if TYPE_CHECKING:
    from langfuse import Langfuse


def _init_client() -> "Langfuse | None":
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None
    try:
        from langfuse import Langfuse  # noqa: PLC0415

        client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            base_url=settings.langfuse_base_url,
        )
        logger.info("Langfuse tracing enabled (base_url={})", settings.langfuse_base_url)
        return client
    except ImportError:
        logger.warning("langfuse package not installed — tracing disabled")
        return None
    except Exception as exc:
        logger.warning("Failed to initialize Langfuse: {}", exc)
        return None


_client: Langfuse | None = None


def get_langfuse() -> "Langfuse | None":
    global _client
    if _client is None:
        _client = _init_client()
    return _client


def flush_langfuse() -> None:
    """Flush pending events to Langfuse (call on app shutdown)."""
    client = get_langfuse()
    if client is not None:
        client.flush()
