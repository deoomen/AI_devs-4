import time
from collections import defaultdict
from dataclasses import dataclass, field

from src.config import settings


@dataclass
class _Window:
    count: int = 0
    reset_at: float = 0.0


class RateLimiter:
    def __init__(self, rpm: int | None = None):
        self._rpm = rpm or settings.agent_rate_limit_rpm
        self._windows: dict[str, _Window] = defaultdict(_Window)

    def check(self, user_id: str) -> bool:
        now = time.monotonic()
        window = self._windows[user_id]
        if now >= window.reset_at:
            window.count = 0
            window.reset_at = now + 60.0
        window.count += 1
        return window.count <= self._rpm


rate_limiter = RateLimiter()
