from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict

from ..config import load_config
from ..dlp.scanner import DLPScanner
from ..exceptions import InputBlockedError, OutputBlockedError, ToolBlockedError
from ..guardrails.engine import GuardrailsEngine
from ..models import DLPAction, GuardrailAction, RequestContext
from ..telemetry import GovernanceLogger, init_telemetry
from ..telemetry.tracing import init_tracing
from ..telemetry.spans import start_span


def attach_adk_hooks(logger: GovernanceLogger, agent_identity) -> Dict[str, Any]:
    """Return hook callbacks for ADK lifecycle integration."""
    def _on_start():
        logger.agent_request_start(agent_identity, RequestContext(), source="adk")

    def _on_end():
        logger.agent_request_end(agent_identity, RequestContext(), status="success", latency_ms=0)

    return {"on_start": _on_start, "on_end": _on_end}


class GovernanceADKMiddleware:
    """ADK middleware that enforces governance on every agent interaction."""

    def __init__(self, config):
        self._config = config
        self._logger = init_telemetry(config.section("telemetry"))
        init_tracing(config.agent, config.section("telemetry"))
        guardrails_cfg = config.section("guardrails")
        self._guardrails_enabled = bool(guardrails_cfg.get("enabled", True))
        self._guardrails_policy = guardrails_cfg.get("policy_file") or guardrails_cfg.get("policy_path") or "inline_or_default"
        self._guardrails_policy_fingerprint = _policy_fingerprint(guardrails_cfg)
        self._guardrails = GuardrailsEngine(guardrails_cfg, self._logger)
        dlp_cfg = config.section("dlp")
        self._dlp = DLPScanner.from_config(dlp_cfg) if dlp_cfg.get("enabled", True) else None
        self._active_spans = {}
        self._tool_spans = {}
        self._emit_guardrails_status()

    @property
    def agent(self):
        return self._config.agent

    @classmethod
    def from_config(
        cls,
        config_path: str | None = None,
        guardrails_path: str | None = None,
    ) -> "GovernanceADKMiddleware":
        return cls(load_config(config_path, guardrails_path=guardrails_path))

    async def before_agent_call(
        self, agent_identity, user_input: str, user_id: str | None = None, session_id: str | None = None
    ) -> tuple[str, RequestContext, float]:
        ctx = RequestContext(
            user_id_hash=RequestContext.hash_user_id(user_id) if user_id else None,
            session_id=session_id,
        )
        start_time = time.monotonic()
        span_ctx = start_span("agent_request", {"agent_id": agent_identity.agent_id})
        span = span_ctx.__enter__()
        self._active_spans[ctx.request_id] = (span_ctx, span)
        self._logger.agent_request_start(
            agent_identity,
            ctx,
            source="adk",
            guardrails_enabled=self._guardrails_enabled,
            guardrails_policy=self._guardrails_policy,
            guardrails_policy_fingerprint=self._guardrails_policy_fingerprint,
        )

        guard = await self._guardrails.check_input(ctx, user_input, agent=agent_identity)
        if guard.action == GuardrailAction.BLOCK:
            raise InputBlockedError(guard.reason)

        if self._dlp and self._config.section("dlp").get("scan_input", True):
            action = DLPAction(self._config.section("dlp").get("action_on_input_pii", "log"))
            user_input, _ = self._dlp.scan_and_process(user_input, action)

        return user_input, ctx, start_time

    async def before_tool_call(
        self, agent_identity, ctx: RequestContext, tool_name: str, tool_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        guard = await self._guardrails.check_tool_call(ctx, tool_name, tool_params, agent=agent_identity)
        if guard.action == GuardrailAction.BLOCK:
            raise ToolBlockedError(f"Tool '{tool_name}' blocked: {guard.reason}")
        if guard.action == GuardrailAction.CONFIRM:
            raise ToolBlockedError(f"Tool '{tool_name}' requires confirmation: {guard.reason}")

        self._logger.tool_call_start(agent_identity, ctx, tool_name)
        tool_span_ctx = start_span("tool_call", {"tool_name": tool_name})
        tool_span = tool_span_ctx.__enter__()
        key = f"{ctx.request_id}:{tool_name}:{len(self._tool_spans)}"
        self._tool_spans[key] = (tool_span_ctx, tool_span)

        if self._dlp and self._config.section("dlp").get("scan_tool_params", True):
            action = DLPAction(self._config.section("dlp").get("action_on_input_pii", "log"))
            _, scan = self._dlp.scan_and_process(str(tool_params), action)
            if action == DLPAction.BLOCK and scan.findings:
                raise ToolBlockedError("Tool params blocked by DLP")

        return tool_params

    async def after_tool_call(
        self,
        agent_identity,
        ctx: RequestContext,
        tool_name: str,
        result: Any,
        latency_ms: int,
        success: bool,
        error: str | None = None,
    ) -> Any:
        self._guardrails.record_tool_result(tool_name, success)
        status = "success" if success else "error"
        self._logger.tool_call_end(agent_identity, ctx, tool_name, status, latency_ms, error_message=error)
        for key, (tool_span_ctx, tool_span) in list(self._tool_spans.items()):
            if key.startswith(f"{ctx.request_id}:{tool_name}:"):
                tool_span.set_attribute("status", status)
                tool_span_ctx.__exit__(None, None, None)
                self._tool_spans.pop(key, None)
                break
        return result

    async def after_agent_call(
        self, agent_identity, ctx: RequestContext, output: str, start_time: float
    ) -> str:
        guard = await self._guardrails.check_output(ctx, output, agent=agent_identity)
        if guard.action == GuardrailAction.BLOCK:
            raise OutputBlockedError(guard.reason)

        if self._dlp and self._config.section("dlp").get("scan_output", True):
            action = DLPAction(self._config.section("dlp").get("action_on_output_pii", "log"))
            output, scan = self._dlp.scan_and_process(output, action)
            if action == DLPAction.BLOCK and scan.findings:
                raise OutputBlockedError("Output blocked by DLP")

        latency_ms = int((time.monotonic() - start_time) * 1000)
        self._logger.agent_request_end(agent_identity, ctx, status="success", latency_ms=latency_ms)
        if ctx.request_id in self._active_spans:
            span_ctx, span = self._active_spans.pop(ctx.request_id)
            span.set_attribute("latency_ms", latency_ms)
            span_ctx.__exit__(None, None, None)
        return output

    def _emit_guardrails_status(self) -> None:
        ctx = RequestContext()
        self._logger.safety_event(
            self.agent,
            ctx,
            event_name="guardrails_policy_loaded",
            action="allow" if self._guardrails_enabled else "block",
            rule_name="guardrails_policy",
            guardrails_enabled=self._guardrails_enabled,
            guardrails_policy=self._guardrails_policy,
            guardrails_policy_fingerprint=self._guardrails_policy_fingerprint,
        )
        if not self._guardrails_enabled:
            self._logger.error_event(
                self.agent,
                ctx,
                message="Guardrails are disabled for this agent",
                severity="critical",
                alert_type="guardrails_disabled",
                guardrails_enabled=False,
                guardrails_policy=self._guardrails_policy,
                guardrails_policy_fingerprint=self._guardrails_policy_fingerprint,
            )


def _policy_fingerprint(policy: Dict[str, Any]) -> str:
    serialized = json.dumps(policy, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
