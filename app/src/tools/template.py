"""Resolve {{PLACEHOLDER}} variables at tool execution boundaries.

Secrets are resolved ONLY in tool arguments right before execution — never in
messages stored in the DB or sent to the LLM.
"""

import re
from typing import Any

from loguru import logger

from src.config import settings

_PATTERN = re.compile(r"\{\{(\w+)\}\}")


def _resolve_string(text: str) -> str:
    template_vars = settings.get_template_vars()

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        value = template_vars.get(key)
        if value is None:
            logger.warning("Unresolved template variable: {{{{{key}}}}} — not in whitelist", key=key)
            return match.group(0)
        return value

    return _PATTERN.sub(_replace, text)


def resolve_args(arguments: Any) -> Any:
    """Recursively resolve {{VAR}} placeholders in tool arguments."""
    if isinstance(arguments, str):
        return _resolve_string(arguments)
    if isinstance(arguments, dict):
        return {k: resolve_args(v) for k, v in arguments.items()}
    if isinstance(arguments, list):
        return [resolve_args(item) for item in arguments]
    return arguments
