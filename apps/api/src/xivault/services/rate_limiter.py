"""Rate limiter implementing sliding window limits."""

import time
from collections import defaultdict

from xivault.exceptions import RateLimitedException


class SlidingWindowRateLimiter:
    """In-memory sliding window rate limiter with bounded memory and stale key pruning."""

    def __init__(self, max_tracked_keys: int = 5000) -> None:
        # key -> list of timestamps
        self.windows: dict[str, list[float]] = defaultdict(list)
        self.max_tracked_keys = max_tracked_keys

    def check(self, key: str, max_requests: int, window_seconds: int) -> None:
        """Check and record an action, raising RateLimitedException if limit exceeded."""
        now = time.time()
        cutoff = now - window_seconds

        # Prune old entries for the specific key
        valid_timestamps = [ts for ts in self.windows.get(key, []) if ts > cutoff]
        if len(valid_timestamps) >= max_requests:
            self.windows[key] = valid_timestamps
            raise RateLimitedException(
                f"Rate limit of {max_requests} per {max(1, window_seconds // 60)}m reached."
            )

        valid_timestamps.append(now)
        self.windows[key] = valid_timestamps

        # Memory leak safeguard: prune expired keys when map exceeds bounded capacity
        if len(self.windows) > self.max_tracked_keys:
            self.prune_stale(now)

    def prune_stale(self, now: float | None = None) -> None:
        """Purge keys whose timestamps have all expired (older than 1 hour)."""
        curr = now if now is not None else time.time()
        cutoff = curr - 3600
        stale_keys = [
            k for k, timestamps in self.windows.items()
            if not timestamps or timestamps[-1] < cutoff
        ]
        for k in stale_keys:
            self.windows.pop(k, None)

    def reset(self) -> None:
        """Clear rate limit history (useful for test suites)."""
        self.windows.clear()


rate_limiter = SlidingWindowRateLimiter()
