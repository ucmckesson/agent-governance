from __future__ import annotations

import time
from typing import Dict

from ..models import GuardrailAction, GuardrailResult


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


class CircuitBreakerRegistry:
    def __init__(self, config: Dict[str, object]) -> None:
        tools_cfg = config.get("tools", {})
        default_policy = tools_cfg.get("default_policy", {})
        self._default_threshold = int(default_policy.get("circuit_breaker_threshold", 5))
        self._tools: Dict[str, CircuitBreaker] = {}
        for policy in tools_cfg.get("policies", []) or []:
            tool_name = policy.get("tool_name")
            threshold = int(policy.get("circuit_breaker_threshold", self._default_threshold))
            self._tools[tool_name] = CircuitBreaker(max_failures=threshold)

    def check(self, tool_name: str) -> GuardrailResult:
        cb = self._tools.get(tool_name)
        if cb and cb.is_open():
            return GuardrailResult(
                action=GuardrailAction.BLOCK,
                rule_name="circuit_open",
                reason=f"Circuit breaker open for {tool_name}",
            )
        return GuardrailResult(action=GuardrailAction.ALLOW, rule_name="circuit_ok", reason="OK")

    def record_success(self, tool_name: str) -> None:
        cb = self._tools.get(tool_name)
        if cb:
            cb.record_success()

    def record_failure(self, tool_name: str) -> None:
        cb = self._tools.get(tool_name)
        if cb:
            cb.record_failure()
