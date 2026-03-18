"""Centralized logging with loguru.

Call ``setup_logging()`` once at app startup.
All modules should use:  ``from loguru import logger``
"""

import logging
import re
import sys

from loguru import logger

from src.config import ROOT_DIR

_LOG_DIR = ROOT_DIR / "logs"

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
CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DDTHH:mm:ss.SSSZ}</green> | "
    "<level>{level: <8}</level> | "
    "<dim>pid:{process} tid:{thread}</dim> | "
    "<dim>{elapsed}</dim> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
    "{message}"
)

FILE_FORMAT = (
    "{time:YYYY-MM-DDTHH:mm:ss.SSSZ} | "
    "{level: <8} | "
    "pid:{process} tid:{thread} | "
    "{elapsed} | "
    "{name}:{function}:{line} — "
    "{message}"
)


def setup_logging(level: str = "INFO") -> None:
    """Configure loguru as the sole logging sink with redaction."""
    logger.remove()

    # Console sink (colorized, redacted)
    logger.add(
        _sink,
        level=level.upper(),
        format=CONSOLE_FORMAT,
        colorize=True,
    )

    # File sink (plain text, redacted, rotating)
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.add(
        _LOG_DIR / "app.log",
        level=level.upper(),
        format=FILE_FORMAT,
        rotation="00:00",
        retention="7 days",
        compression="gz",
        encoding="utf-8",
        filter=lambda record: _redact_record(record),
    )

    # Redirect stdlib logging through loguru
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)

    # Quiet noisy third-party stdlib loggers
    for name in ("httpx", "httpcore", "hpack", "asyncio"):
        logging.getLogger(name).setLevel(logging.WARNING)


def _redact_record(record) -> bool:
    """Mutate the record message in-place for file sink redaction."""
    record["message"] = _redact(record["message"])
    return True
