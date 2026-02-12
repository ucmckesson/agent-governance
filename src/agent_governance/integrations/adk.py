from __future__ import annotations

import time
from typing import Any, Dict

from ..config import load_config
from ..dlp.scanner import DLPScanner
from ..exceptions import InputBlockedError, OutputBlockedError, ToolBlockedError
from ..guardrails.engine import GuardrailsEngine
from ..models import DLPAction, GuardrailAction, RequestContext
from ..telemetry import GovernanceLogger, init_telemetry


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
        self._guardrails = GuardrailsEngine(config.section("guardrails"), self._logger)
        dlp_cfg = config.section("dlp")
        self._dlp = DLPScanner.from_config(dlp_cfg) if dlp_cfg.get("enabled", True) else None

    @property
    def agent(self):
        return self._config.agent

    @classmethod
    def from_config(cls, config_path: str | None = None) -> "GovernanceADKMiddleware":
        return cls(load_config(config_path))

    async def before_agent_call(
        self, agent_identity, user_input: str, user_id: str | None = None, session_id: str | None = None
    ) -> tuple[str, RequestContext, float]:
        ctx = RequestContext(
            user_id_hash=RequestContext.hash_user_id(user_id) if user_id else None,
            session_id=session_id,
        )
        start_time = time.monotonic()
        self._logger.agent_request_start(agent_identity, ctx, source="adk")

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
        return output
