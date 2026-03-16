"""Centralized logging with loguru.

Call ``setup_logging()`` once at app startup.
All modules should use:  ``from loguru import logger``
"""

import logging
import re
import sys

from loguru import logger

# ---------------------------------------------------------------------------
# Sensitive-key redaction
# ---------------------------------------------------------------------------
# Matches key=value or "key": "value" patterns where the key looks sensitive.
_SENSITIVE_RE = re.compile(
    r"""(?i)(['"]?"""
    r"""(?:api_?key|token|secret|password|passwd|credentials|apikey)"""
    r"""['"]?)"""
    r"""(\s*[:=]\s*)"""
    r"""(['"]?)([^'"\s},\]]{4,})(['"]?)""",
)

# Matches "Bearer <token>" or "Basic <token>" (e.g. Authorization headers).
_BEARER_RE = re.compile(r"(?i)(Bearer|Basic)\s+\S+")


def _redact(text: str) -> str:
    text = _BEARER_RE.sub(r"\1 ***", text)
    return _SENSITIVE_RE.sub(r"\1\2\3***\5", text)


def _sink(message):
    sys.stderr.write(_redact(str(message)))


# ---------------------------------------------------------------------------
# stdlib → loguru bridge
# ---------------------------------------------------------------------------
class _InterceptHandler(logging.Handler):
    """Forward stdlib log records to loguru so uvicorn/sqlalchemy/httpx logs
    are formatted and redacted consistently."""

    def emit(self, record: logging.LogRecord):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)


def setup_logging(level: str = "INFO") -> None:
    """Configure loguru as the sole logging sink with redaction."""
    logger.remove()
    logger.add(
        _sink,
        level=level.upper(),
        format=LOG_FORMAT,
        colorize=True,
    )

    # Redirect stdlib logging through loguru
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)

    # Quiet noisy third-party stdlib loggers
    for name in ("httpx", "httpcore", "hpack", "asyncio"):
        logging.getLogger(name).setLevel(logging.WARNING)
