"""Simple async rate limiter for API calls."""

import asyncio
import time
from collections import defaultdict


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, rate: float = 10.0, per: float = 1.0):
        self.rate = rate
        self.per = per
        self._allowance: dict[str, float] = defaultdict(lambda: rate)
        self._last_check: dict[str, float] = defaultdict(time.monotonic)
        self._lock = asyncio.Lock()

    async def acquire(self, key: str = "default"):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_check[key]
            self._last_check[key] = now
            self._allowance[key] += elapsed * (self.rate / self.per)
            if self._allowance[key] > self.rate:
                self._allowance[key] = self.rate

            if self._allowance[key] < 1.0:
                wait = (1.0 - self._allowance[key]) * (self.per / self.rate)
                await asyncio.sleep(wait)
                self._allowance[key] = 0.0
            else:
                self._allowance[key] -= 1.0
