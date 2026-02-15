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
from ..telemetry.cost_tracker import CostTracker
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
        tracing_cfg = (config.section("telemetry") or {}).get("tracing", {})
        session_tracking_cfg = tracing_cfg.get("session_tracking", {}) if isinstance(tracing_cfg, dict) else {}
        self._session_tracking_enabled = bool(session_tracking_cfg.get("enabled", True))
        self._session_attr = str(session_tracking_cfg.get("session_attribute", "governance.session_id"))
        self._user_attr = str(session_tracking_cfg.get("user_attribute", "governance.user_id"))
        guardrails_cfg = config.section("guardrails")
        self._guardrails_enabled = bool(guardrails_cfg.get("enabled", True))
        self._guardrails_policy = guardrails_cfg.get("policy_file") or guardrails_cfg.get("policy_path") or "inline_or_default"
        self._guardrails_policy_fingerprint = _policy_fingerprint(guardrails_cfg)
        self._guardrails = GuardrailsEngine(guardrails_cfg, self._logger)
        dlp_cfg = config.section("dlp")
        self._dlp = DLPScanner.from_config(dlp_cfg) if dlp_cfg.get("enabled", True) else None
        self._active_spans = {}
        self._tool_spans = {}
        self._request_metrics: Dict[str, Dict[str, Any]] = {}
        self._session_turns: Dict[str, int] = {}
        telemetry_cfg = config.section("telemetry") or {}
        self._cost_tracker = CostTracker(telemetry_cfg.get("cost_tracking", {}))
        self._prompt_fingerprint: str | None = None
        self._prompt_length_chars: int | None = None
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
        self,
        agent_identity,
        user_input: str,
        user_id: str | None = None,
        session_id: str | None = None,
        prompt_text: str | None = None,
    ) -> tuple[str, RequestContext, float]:
        ctx = RequestContext(
            user_id_hash=RequestContext.hash_user_id(user_id) if user_id else None,
            session_id=session_id,
        )
        start_time = time.monotonic()
        if prompt_text is not None:
            self.set_prompt(prompt_text)

        span_attrs = {
            "agent_id": agent_identity.agent_id,
            **self._session_span_attrs(ctx),
            **self._prompt_attrs(),
        }
        span_ctx = start_span("agent_request", span_attrs)
        span = span_ctx.__enter__()
        self._active_spans[ctx.request_id] = (span_ctx, span)
        session_turn = self._record_turn(ctx)
        self._request_metrics[ctx.request_id] = {
            "tool_calls": 0,
            "delegation_hops": 0,
            "delegation_chain": "",
            "llm_calls": 0,
            "llm_input_tokens": 0,
            "llm_output_tokens": 0,
            "session_turn": session_turn,
        }
        self._logger.agent_request_start(
            agent_identity,
            ctx,
            source="adk",
            guardrails_enabled=self._guardrails_enabled,
            guardrails_policy=self._guardrails_policy,
            guardrails_policy_fingerprint=self._guardrails_policy_fingerprint,
            session_turn=session_turn,
            **self._prompt_attrs(),
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

        metrics = self._request_metrics.get(ctx.request_id)
        if metrics is not None:
            metrics["tool_calls"] = int(metrics.get("tool_calls", 0)) + 1

        self._logger.tool_call_start(agent_identity, ctx, tool_name)
        tool_span_ctx = start_span("tool_call", {"tool_name": tool_name, **self._session_span_attrs(ctx)})
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
        request_cost_usd = self._cost_tracker.finalize_request(ctx.request_id) if self._cost_tracker.enabled else 0.0
        request_metrics = self._request_metrics.pop(ctx.request_id, {})
        self._logger.agent_request_end(
            agent_identity,
            ctx,
            status="success",
            latency_ms=latency_ms,
            total_request_cost_usd=request_cost_usd,
            tool_calls=int(request_metrics.get("tool_calls", 0)),
            delegation_hops=int(request_metrics.get("delegation_hops", 0)),
            delegation_chain=str(request_metrics.get("delegation_chain", "")),
            llm_calls=int(request_metrics.get("llm_calls", 0)),
            llm_input_tokens=int(request_metrics.get("llm_input_tokens", 0)),
            llm_output_tokens=int(request_metrics.get("llm_output_tokens", 0)),
            session_turn=int(request_metrics.get("session_turn", 0)),
            **self._prompt_attrs(),
        )
        if ctx.request_id in self._active_spans:
            span_ctx, span = self._active_spans.pop(ctx.request_id)
            span.set_attribute("latency_ms", latency_ms)
            if self._cost_tracker.enabled:
                span.set_attribute("governance.cost.total_request_usd", request_cost_usd)
            span.set_attribute("governance.delegation.hop_number", int(request_metrics.get("delegation_hops", 0)))
            span.set_attribute("governance.agent.tool_calls", int(request_metrics.get("tool_calls", 0)))
            span.set_attribute("governance.agent.session_turn", int(request_metrics.get("session_turn", 0)))
            span_ctx.__exit__(None, None, None)
        return output

    async def record_llm_usage(
        self,
        agent_identity,
        ctx: RequestContext,
        *,
        model: str,
        input_tokens: int,
        output_tokens: int,
        delegation_chain: str | None = None,
    ) -> Dict[str, float]:
        if not self._cost_tracker.enabled:
            return {"request_total_usd": 0.0, "session_total_usd": 0.0}

        usage = self._cost_tracker.estimate(model, input_tokens, output_tokens)
        totals = self._cost_tracker.record(ctx.request_id, ctx.session_id, usage)
        metrics = self._request_metrics.get(ctx.request_id)
        if metrics is not None:
            metrics["llm_calls"] = int(metrics.get("llm_calls", 0)) + 1
            metrics["llm_input_tokens"] = int(metrics.get("llm_input_tokens", 0)) + usage.input_tokens
            metrics["llm_output_tokens"] = int(metrics.get("llm_output_tokens", 0)) + usage.output_tokens

        self._logger.cost_event(
            agent_identity,
            ctx,
            model=usage.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            estimated_usd=usage.estimated_usd,
            total_request_usd=totals["request_total_usd"],
            total_session_usd=totals["session_total_usd"],
            delegation_chain=delegation_chain,
        )

        with start_span(
            "llm_cost",
            {
                "governance.cost.model": usage.model,
                "governance.cost.input_tokens": str(usage.input_tokens),
                "governance.cost.output_tokens": str(usage.output_tokens),
                "governance.cost.estimated_usd": str(usage.estimated_usd),
                **self._session_span_attrs(ctx),
            },
        ):
            pass

        threshold = self._cost_tracker.threshold_usd
        if threshold > 0 and totals["request_total_usd"] > threshold:
            self._logger.error_event(
                agent_identity,
                ctx,
                message="Request cost threshold exceeded",
                severity="warning",
                alert_type="high_request_cost",
                threshold_usd=threshold,
                total_request_usd=totals["request_total_usd"],
                model=model,
            )

        return totals

    async def record_delegation(
        self,
        agent_identity,
        ctx: RequestContext,
        *,
        source_agent: str,
        target_agent: str,
        reason: str | None = None,
        hop_number: int | None = None,
        chain: list[str] | None = None,
        method: str = "sub_agent",
    ) -> None:
        chain_str = "→".join(chain) if chain else None
        self._logger.agent_delegation(
            agent_identity,
            ctx,
            source_agent=source_agent,
            target_agent=target_agent,
            reason=reason,
            hop_number=hop_number,
            chain=chain_str,
            method=method,
        )
        attrs = {
            "governance.delegation.source_agent": source_agent,
            "governance.delegation.target_agent": target_agent,
            "governance.delegation.method": method,
            **self._session_span_attrs(ctx),
        }
        if reason is not None:
            attrs["governance.delegation.reason"] = reason
        if hop_number is not None:
            attrs["governance.delegation.hop_number"] = hop_number
        if chain_str is not None:
            attrs["governance.delegation.chain"] = chain_str
        with start_span("agent_delegation", attrs):
            pass
        metrics = self._request_metrics.get(ctx.request_id)
        if metrics is not None:
            metrics["delegation_hops"] = int(metrics.get("delegation_hops", 0)) + 1
            if chain_str:
                metrics["delegation_chain"] = chain_str

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

    def _session_span_attrs(self, ctx: RequestContext) -> Dict[str, str]:
        if not self._session_tracking_enabled:
            return {}
        attrs: Dict[str, str] = {}
        if ctx.session_id:
            attrs[self._session_attr] = ctx.session_id
        if ctx.user_id_hash:
            attrs[self._user_attr] = ctx.user_id_hash
        return attrs

    def set_prompt(self, prompt_text: str) -> None:
        self._prompt_length_chars = len(prompt_text or "")
        self._prompt_fingerprint = _prompt_fingerprint(prompt_text)

    def _prompt_attrs(self) -> Dict[str, Any]:
        attrs: Dict[str, Any] = {}
        if self._prompt_fingerprint:
            attrs["prompt_fingerprint"] = self._prompt_fingerprint
        if self._prompt_length_chars is not None:
            attrs["prompt_length_chars"] = self._prompt_length_chars
        return attrs

    def _record_turn(self, ctx: RequestContext) -> int:
        if not ctx.session_id:
            return 0
        turn = int(self._session_turns.get(ctx.session_id, 0)) + 1
        self._session_turns[ctx.session_id] = turn
        return turn


def _policy_fingerprint(policy: Dict[str, Any]) -> str:
    serialized = json.dumps(policy, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def _prompt_fingerprint(prompt_text: str | None) -> str:
    text = prompt_text or ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
