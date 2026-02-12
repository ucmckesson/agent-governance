from __future__ import annotations

from typing import Any, Dict

from ..models import GuardrailAction, GuardrailResult
from .circuit_breaker import CircuitBreaker
from .content_filter import ContentFilter
from .input_validator import InputValidator
from .output_validator import OutputValidator
from .rate_limiter import RateLimiter
from .tool_policy import ToolPolicy


class GuardrailsEngine:
    """Orchestrates guardrail checks. Fail-closed on internal errors."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.tool_policy = ToolPolicy(
            allowlist=config.get("tool_allowlist"),
            denylist=config.get("tool_denylist"),
        )
        self.input_validator = InputValidator()
        self.output_validator = OutputValidator()
        self.rate_limiter = RateLimiter(max_calls_per_minute=int(config.get("max_calls_per_minute", 60)))
        self.content_filter = ContentFilter(config.get("content_blocklist"))
        self.circuit_breaker = CircuitBreaker()

    def validate_tool_call(self, tool_name: str, payload: Dict[str, Any], rate_key: str) -> GuardrailResult:
        try:
            if self.circuit_breaker.is_open():
                return GuardrailResult(action=GuardrailAction.BLOCK, reason="circuit_open")

            if not self.tool_policy.is_allowed(tool_name):
                return GuardrailResult(action=GuardrailAction.BLOCK, reason="tool_not_allowed")

            if not self.rate_limiter.allow(rate_key):
                return GuardrailResult(action=GuardrailAction.BLOCK, reason="rate_limited")

            ok, reason = self.input_validator.validate(payload)
            if not ok:
                return GuardrailResult(action=GuardrailAction.BLOCK, reason=reason)

            if not self.content_filter.is_safe(str(payload)):
                return GuardrailResult(action=GuardrailAction.BLOCK, reason="content_blocked")

            return GuardrailResult(action=GuardrailAction.ALLOW, reason="ok")
        except Exception:
            self.circuit_breaker.record_failure()
            return GuardrailResult(action=GuardrailAction.BLOCK, reason="guardrail_error")

    def validate_output(self, output: Dict[str, Any]) -> GuardrailResult:
        try:
            ok, reason = self.output_validator.validate(output)
            if not ok:
                return GuardrailResult(action=GuardrailAction.BLOCK, reason=reason)
            if not self.content_filter.is_safe(str(output)):
                return GuardrailResult(action=GuardrailAction.BLOCK, reason="content_blocked")
            self.circuit_breaker.record_success()
            return GuardrailResult(action=GuardrailAction.ALLOW, reason="ok")
        except Exception:
            self.circuit_breaker.record_failure()
            return GuardrailResult(action=GuardrailAction.BLOCK, reason="guardrail_error")
