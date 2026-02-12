from __future__ import annotations

import time


class CircuitBreaker:
    def __init__(self, max_failures: int = 5, reset_seconds: int = 60) -> None:
        self.max_failures = max_failures
        self.reset_seconds = reset_seconds
        self._failures = 0
        self._opened_at: float | None = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.max_failures:
            self._opened_at = time.time()

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.time() - self._opened_at > self.reset_seconds:
            self.record_success()
            return False
        return True
