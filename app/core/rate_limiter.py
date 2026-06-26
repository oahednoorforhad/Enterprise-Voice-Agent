"""In-memory rate limiter per customer action.

Uses asyncio.Lock for thread-safe check-and-set.
"""

import asyncio
from datetime import UTC, datetime, timedelta


class RateLimiter:
    """Rate limiter that limits actions per customer within a sliding window.

    Args:
        max_requests: Maximum allowed actions in the window (default 1).
        window_seconds: Length of the sliding window in seconds (default 300 = 5 min).
    """

    def __init__(self, max_requests: int = 1, window_seconds: int = 300) -> None:
        self._max = max_requests
        self._window = timedelta(seconds=window_seconds)
        self._store: dict[str, list[datetime]] = {}
        self._lock = asyncio.Lock()

    async def check_and_increment(self, customer_id: str) -> tuple[bool, int]:
        """Check if customer is allowed and record the attempt.

        Returns (allowed, seconds_until_available).
        """
        async with self._lock:
            now = datetime.now(UTC)
            if customer_id not in self._store:
                self._store[customer_id] = []
            # Prune expired entries
            cutoff = now - self._window
            self._store[customer_id] = [t for t in self._store[customer_id] if t > cutoff]
            if len(self._store[customer_id]) >= self._max:
                oldest = self._store[customer_id][0]
                wait = int((oldest + self._window - now).total_seconds())
                return False, max(wait, 0)
            self._store[customer_id].append(now)
            return True, 0

    async def reset(self) -> None:
        """Clear all rate limit state (for test isolation)."""
        async with self._lock:
            self._store.clear()


# Singleton instance
rate_limiter = RateLimiter()
