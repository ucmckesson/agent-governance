from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict

from ..models import GuardrailAction, GuardrailResult


class RateLimiter:
    def __init__(self, config: Dict[str, object]) -> None:
        cfg = config.get("rate_limiting", {})
        self.enabled = bool(cfg.get("enabled", True))
        self.user_limit = int(cfg.get("requests_per_minute_per_user", 30))
        self.global_limit = int(cfg.get("requests_per_minute_global", 500))
        self._buckets = defaultdict(list)

    def check(self, user_key: str | None) -> GuardrailResult:
        if not self.enabled:
            return GuardrailResult(action=GuardrailAction.ALLOW, rule_name="rate_limit_disabled", reason="OK")
        if user_key:
            if not self._allow(f"user:{user_key}", self.user_limit):
                return GuardrailResult(
                    action=GuardrailAction.BLOCK,
                    rule_name="rate_limit_user",
                    reason="User rate limit exceeded",
                )
        if not self._allow("global", self.global_limit):
            return GuardrailResult(
                action=GuardrailAction.BLOCK,
                rule_name="rate_limit_global",
                reason="Global rate limit exceeded",
            )
        return GuardrailResult(action=GuardrailAction.ALLOW, rule_name="rate_limit_ok", reason="OK")

    def _allow(self, key: str, max_calls: int) -> bool:
        now = time.time()
        window_start = now - 60
        calls = self._buckets[key]
        while calls and calls[0] < window_start:
            calls.pop(0)
        if len(calls) >= max_calls:
            return False
        calls.append(now)
        return True
