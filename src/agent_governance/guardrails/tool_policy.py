from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict

from ..models import GuardrailAction, GuardrailResult


class ToolPolicyEnforcer:
    """Enforces tool-level policies from governance.yaml."""

    def __init__(self, config: Dict[str, Any]) -> None:
        tools_cfg = config.get("tools", {})
        default_policy = tools_cfg.get("default_policy", {})
        self._default_allowed = bool(default_policy.get("allowed", False))
        self._policies: Dict[str, Dict[str, Any]] = {}
        for policy in tools_cfg.get("policies", []) or []:
            self._policies[policy.get("tool_name")] = policy
        self._request_call_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def check_allowed(self, tool_name: str) -> GuardrailResult:
        policy = self._policies.get(tool_name)
        if not policy:
            if self._default_allowed:
                return GuardrailResult(
                    action=GuardrailAction.ALLOW,
                    rule_name="default_allow",
                    reason=f"Tool '{tool_name}' allowed by default policy",
                )
            return GuardrailResult(
                action=GuardrailAction.BLOCK,
                rule_name="tool_not_in_allowlist",
                reason=(
                    f"Tool '{tool_name}' is not in the allowlist. "
                    "Add it to guardrails.tools.policies in governance.yaml to allow it."
                ),
            )

        if not policy.get("allowed", True):
            return GuardrailResult(
                action=GuardrailAction.BLOCK,
                rule_name="tool_explicitly_blocked",
                reason=f"Tool '{tool_name}' is explicitly blocked in governance.yaml",
            )

        return GuardrailResult(
            action=GuardrailAction.ALLOW,
            rule_name="tool_in_allowlist",
            reason=f"Tool '{tool_name}' is in the allowlist",
        )

    def check_call_limit(self, request_id: str, tool_name: str) -> GuardrailResult:
        policy = self._policies.get(tool_name)
        max_calls = policy.get("max_calls_per_request") if policy else None
        if not max_calls:
            return GuardrailResult(action=GuardrailAction.ALLOW, rule_name="no_call_limit", reason="No call limit")

        self._request_call_counts[request_id][tool_name] += 1
        count = self._request_call_counts[request_id][tool_name]
        if count > max_calls:
            return GuardrailResult(
                action=GuardrailAction.BLOCK,
                rule_name="tool_call_limit_exceeded",
                reason=(
                    f"Tool '{tool_name}' exceeded max {max_calls} calls per request "
                    f"(attempted call #{count})"
                ),
            )
        return GuardrailResult(
            action=GuardrailAction.ALLOW,
            rule_name="within_call_limit",
            reason=f"Call {count}/{max_calls}",
        )

    def check_params(self, tool_name: str, params: Dict[str, Any]) -> GuardrailResult:
        policy = self._policies.get(tool_name)
        if not policy:
            return GuardrailResult(action=GuardrailAction.ALLOW, rule_name="no_param_policy", reason="No policy")

        blocked = policy.get("blocked_params") or {}
        for param_name, blocked_values in blocked.items():
            if param_name in params and str(params[param_name]) in blocked_values:
                return GuardrailResult(
                    action=GuardrailAction.BLOCK,
                    rule_name="blocked_param_value",
                    reason=f"Parameter '{param_name}' has blocked value for tool '{tool_name}'",
                )

        allowed = policy.get("allowed_params") or {}
        for param_name, allowed_values in allowed.items():
            if param_name in params and str(params[param_name]) not in allowed_values:
                return GuardrailResult(
                    action=GuardrailAction.BLOCK,
                    rule_name="param_not_in_allowlist",
                    reason=f"Parameter '{param_name}' value not in allowed list for tool '{tool_name}'",
                )

        return GuardrailResult(action=GuardrailAction.ALLOW, rule_name="params_valid", reason="Parameters valid")

    def check_confirmation_required(self, tool_name: str) -> GuardrailResult:
        policy = self._policies.get(tool_name)
        if policy and policy.get("requires_confirmation"):
            return GuardrailResult(
                action=GuardrailAction.CONFIRM,
                rule_name="confirmation_required",
                reason=(
                    f"Tool '{tool_name}' is marked as destructive and requires human confirmation"
                ),
            )
        return GuardrailResult(action=GuardrailAction.ALLOW, rule_name="no_confirmation", reason="No confirmation")

    def clear_request(self, request_id: str) -> None:
        self._request_call_counts.pop(request_id, None)
