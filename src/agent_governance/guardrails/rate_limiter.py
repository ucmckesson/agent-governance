from __future__ import annotations

import time
from collections import defaultdict


class RateLimiter:
    def __init__(self, max_calls_per_minute: int = 60) -> None:
        self.max_calls = max_calls_per_minute
        self._buckets = defaultdict(list)

    def allow(self, key: str) -> bool:
        now = time.time()
        window_start = now - 60
        calls = self._buckets[key]
        while calls and calls[0] < window_start:
            calls.pop(0)
        if len(calls) >= self.max_calls:
            return False
        calls.append(now)
        return True
