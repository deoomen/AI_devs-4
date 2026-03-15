"""Resolve {{PLACEHOLDER}} variables in user messages before they reach the agent."""

import logging
import re

from src.config import settings

logger = logging.getLogger(__name__)

_PATTERN = re.compile(r"\{\{(\w+)\}\}")


def resolve_vars(message: str) -> str:
    """Replace all whitelisted {{VAR}} placeholders with their values."""
    template_vars = settings.get_template_vars()

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        value = template_vars.get(key)
        if value is None:
            logger.warning("Unresolved template variable: {{%s}} — not in whitelist", key)
            return match.group(0)
        return value

    return _PATTERN.sub(_replace, message)
