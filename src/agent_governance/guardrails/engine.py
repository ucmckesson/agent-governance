from __future__ import annotations

from typing import Any, Dict

from ..models import GuardrailAction, GuardrailResult, RequestContext
from ..telemetry.logger import GovernanceLogger
from .circuit_breaker import CircuitBreakerRegistry
from .content_filter import ContentFilter
from .input_validator import InputValidator
from .model_schema import ModelSchemaValidator
from .output_validator import OutputValidator
from .rate_limiter import RateLimiter
from .tool_policy import ToolPolicyEnforcer


class GuardrailsEngine:
    """Orchestrates guardrail checks. Fail-closed on internal errors."""

    def __init__(self, config: Dict[str, Any], logger: GovernanceLogger | None = None) -> None:
        self._config = config
        self._enabled = bool(config.get("enabled", True))
        self._logger = logger
        self._tool_enforcer = ToolPolicyEnforcer(config)
        self._input_validator = InputValidator(config)
        self._output_validator = OutputValidator(config)
        self._rate_limiter = RateLimiter(config)
        self._content_filter = ContentFilter(config)
        self._circuit_breakers = CircuitBreakerRegistry(config)
        schema_path = config.get("model_schema_file") or config.get("model_schema_path")
        self._schema_validator = ModelSchemaValidator(schema_path) if schema_path else None

    async def check_input(self, ctx: RequestContext, input_text: str, agent=None) -> GuardrailResult:
        if not self._enabled:
            return GuardrailResult(action=GuardrailAction.ALLOW, rule_name="disabled", reason="Guardrails disabled")

        try:
            rate_result = self._rate_limiter.check(ctx.user_id_hash)
            if rate_result.action == GuardrailAction.BLOCK:
                self._emit(agent, ctx, "rate_limited", rate_result)
                return rate_result

            input_result = self._input_validator.validate(input_text)
            if input_result.action == GuardrailAction.BLOCK:
                self._emit(agent, ctx, "input_rejected", input_result)
                return input_result

            inj_result = self._input_validator.check_injection(input_text)
            if inj_result.action == GuardrailAction.BLOCK:
                self._emit(agent, ctx, "injection_detected", inj_result)
                return inj_result

            if self._schema_validator:
                errors = self._schema_validator.validate_input({"text": input_text})
                if errors:
                    result = GuardrailResult(
                        action=GuardrailAction.BLOCK,
                        rule_name="input_schema",
                        reason="Input schema validation failed",
                        details={"errors": errors},
                    )
                    self._emit(agent, ctx, "schema_validation", result)
                    return result

            safety_result = self._content_filter.check(input_text)
            if safety_result.action == GuardrailAction.BLOCK:
                self._emit(agent, ctx, "content_filtered", safety_result)
                return safety_result

            return GuardrailResult(action=GuardrailAction.ALLOW, rule_name="all_passed", reason="OK")
        except Exception:
            return GuardrailResult(action=GuardrailAction.BLOCK, rule_name="guardrail_error", reason="Error")

    async def check_tool_call(
        self,
        ctx: RequestContext,
        tool_name: str,
        tool_params: Dict[str, Any] | None = None,
        agent=None,
    ) -> GuardrailResult:
        if not self._enabled:
            return GuardrailResult(action=GuardrailAction.ALLOW, rule_name="disabled", reason="Guardrails disabled")

        try:
            allow_result = self._tool_enforcer.check_allowed(tool_name)
            if allow_result.action == GuardrailAction.BLOCK:
                self._emit(agent, ctx, "tool_blocked", allow_result, tool_name=tool_name)
                return allow_result

            limit_result = self._tool_enforcer.check_call_limit(ctx.request_id, tool_name)
            if limit_result.action == GuardrailAction.BLOCK:
                self._emit(agent, ctx, "tool_blocked", limit_result, tool_name=tool_name)
                return limit_result

            if tool_params:
                param_result = self._tool_enforcer.check_params(tool_name, tool_params)
                if param_result.action == GuardrailAction.BLOCK:
                    self._emit(agent, ctx, "tool_blocked", param_result, tool_name=tool_name)
                    return param_result

                if self._schema_validator:
                    errors = self._schema_validator.validate_tool_params(tool_name, tool_params)
                    if errors:
                        result = GuardrailResult(
                            action=GuardrailAction.BLOCK,
                            rule_name="tool_schema",
                            reason="Tool params schema validation failed",
                            details={"errors": errors},
                        )
                        self._emit(agent, ctx, "schema_validation", result, tool_name=tool_name)
                        return result

            cb_result = self._circuit_breakers.check(tool_name)
            if cb_result.action == GuardrailAction.BLOCK:
                self._emit(agent, ctx, "tool_blocked", cb_result, tool_name=tool_name)
                return cb_result

            confirm_result = self._tool_enforcer.check_confirmation_required(tool_name)
            if confirm_result.action == GuardrailAction.CONFIRM:
                self._emit(agent, ctx, "confirmation_required", confirm_result, tool_name=tool_name)
                return confirm_result

            return GuardrailResult(action=GuardrailAction.ALLOW, rule_name="all_passed", reason="OK")
        except Exception:
            return GuardrailResult(action=GuardrailAction.BLOCK, rule_name="guardrail_error", reason="Error")

    async def check_output(self, ctx: RequestContext, output_text: str, agent=None) -> GuardrailResult:
        if not self._enabled:
            return GuardrailResult(action=GuardrailAction.ALLOW, rule_name="disabled", reason="Guardrails disabled")
        try:
            length_result = self._output_validator.validate_length(output_text)
            if length_result.action == GuardrailAction.BLOCK:
                self._emit(agent, ctx, "output_filtered", length_result)
                return length_result

            if self._schema_validator:
                errors = self._schema_validator.validate_output({"text": output_text})
                if errors:
                    result = GuardrailResult(
                        action=GuardrailAction.BLOCK,
                        rule_name="output_schema",
                        reason="Output schema validation failed",
                        details={"errors": errors},
                    )
                    self._emit(agent, ctx, "schema_validation", result)
                    return result

            safety_result = self._content_filter.check(output_text)
            if safety_result.action == GuardrailAction.BLOCK:
                self._emit(agent, ctx, "output_filtered", safety_result)
                return safety_result

            return GuardrailResult(action=GuardrailAction.ALLOW, rule_name="all_passed", reason="OK")
        except Exception:
            return GuardrailResult(action=GuardrailAction.BLOCK, rule_name="guardrail_error", reason="Error")

    def record_tool_result(self, tool_name: str, success: bool) -> None:
        if success:
            self._circuit_breakers.record_success(tool_name)
        else:
            self._circuit_breakers.record_failure(tool_name)

    def _emit(self, agent, ctx: RequestContext, event_name: str, result: GuardrailResult, **details) -> None:
        if self._logger and agent:
            self._logger.safety_event(
                agent,
                ctx,
                event_name,
                result.action.value,
                result.rule_name,
                reason=result.reason,
                **details,
            )
