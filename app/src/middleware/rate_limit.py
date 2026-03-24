import math
import time
from collections import defaultdict
from dataclasses import dataclass

from src.config import settings
from src.domain.ids import UserId


@dataclass
class _Window:
    count: int = 0
    reset_at: float = 0.0


@dataclass
class RateLimitInfo:
    allowed: bool
    limit: int
    remaining: int
    reset_seconds: int


class RateLimiter:
    def __init__(self, rpm: int | None = None):
        self._rpm = rpm or settings.agent_rate_limit_rpm
        self._windows: dict[str, _Window] = defaultdict(_Window)

    def check(self, user_id: UserId) -> RateLimitInfo:
        now = time.monotonic()
        window = self._windows[str(user_id)]
        if now >= window.reset_at:
            window.count = 0
            window.reset_at = now + 60.0
        window.count += 1

        remaining = max(0, self._rpm - window.count)
        reset_seconds = math.ceil(window.reset_at - now)

        return RateLimitInfo(
            allowed=window.count <= self._rpm,
            limit=self._rpm,
            remaining=remaining,
            reset_seconds=reset_seconds,
        )

    def cleanup(self) -> None:
        now = time.monotonic()
        expired = [k for k, w in self._windows.items() if now >= w.reset_at]
        for k in expired:
            del self._windows[k]


rate_limiter = RateLimiter()
