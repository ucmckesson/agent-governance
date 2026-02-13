from __future__ import annotations

import json
import logging
import sys
from typing import Any, Dict, Iterable, Optional

from ..exceptions import TelemetryError
from ..models import BaseEvent, EventType, RequestContext
from .buffered_emitter import BufferedEmitter
from .events import build_event
from .cloud_logging import enable_cloud_logging
from .redaction import redact_fields


class GovernanceLogger:
    """Structured JSON logger with optional buffering."""

    def __init__(
        self,
        name: str = "agent_governance",
        redaction_keys: Optional[Iterable[str]] = None,
        buffer_size: int = 0,
        custom_fields: Optional[Dict[str, Any]] = None,
        log_level: str = "INFO",
    ) -> None:
        self._logger = logging.getLogger(name)
        self._logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        self._logger.handlers = [handler]
        self._redaction_keys = set(redaction_keys or [])
        self._emitter = BufferedEmitter(self._emit, buffer_size) if buffer_size > 0 else None
        self._custom_fields = custom_fields or {}

    def emit_event(self, event: BaseEvent) -> None:
        try:
            payload = event.model_dump(mode="json")
            payload.setdefault("attributes", {})
            payload["attributes"].update(self._custom_fields)
            payload = redact_fields(payload, self._redaction_keys)
            if self._emitter:
                self._emitter.enqueue(payload)
            else:
                self._emit(payload)
        except Exception as exc:  # pragma: no cover - defensive
            raise TelemetryError(str(exc)) from exc

    def flush(self) -> None:
        if self._emitter:
            self._emitter.flush()

    def _emit(self, payload: Dict[str, Any]) -> None:
        self._logger.info(json.dumps(payload, separators=(",", ":")))

    def agent_request_start(self, agent, ctx: RequestContext, source: str = "adk") -> None:
        self.emit_event(build_event(EventType.AGENT_REQUEST_START, agent, ctx, {"source": source}))

    def agent_request_end(self, agent, ctx: RequestContext, status: str, latency_ms: int, **metrics) -> None:
        self.emit_event(
            build_event(
                EventType.AGENT_REQUEST_END,
                agent,
                ctx,
                {"status": status, "latency_ms": latency_ms, **metrics},
            )
        )

    def tool_call_start(self, agent, ctx: RequestContext, tool_name: str) -> None:
        self.emit_event(build_event(EventType.TOOL_CALL_START, agent, ctx, {"tool_name": tool_name}))

    def tool_call_end(
        self,
        agent,
        ctx: RequestContext,
        tool_name: str,
        status: str,
        latency_ms: int,
        error_message: Optional[str] = None,
    ) -> None:
        payload = {
            "tool_name": tool_name,
            "status": status,
            "latency_ms": latency_ms,
        }
        if error_message:
            payload["error_message"] = error_message
        self.emit_event(build_event(EventType.TOOL_CALL_END, agent, ctx, payload))

    def safety_event(
        self,
        agent,
        ctx: RequestContext,
        event_name: str,
        action: str,
        rule_name: str,
        **details,
    ) -> None:
        self.emit_event(
            build_event(
                EventType.SAFETY_EVENT,
                agent,
                ctx,
                {"event": event_name, "action": action, "rule_name": rule_name, **details},
            )
        )

    def error_event(self, agent, ctx: RequestContext, message: str, **details) -> None:
        self.emit_event(build_event(EventType.ERROR_EVENT, agent, ctx, {"message": message, **details}))

    def registration_event(self, agent, ctx: RequestContext, status: str, **details) -> None:
        self.emit_event(build_event(EventType.REGISTRATION_EVENT, agent, ctx, {"status": status, **details}))


def init_telemetry(config: Dict[str, Any]) -> GovernanceLogger:
    redaction_keys = config.get("redact_fields") or config.get("redaction_keys", [])
    custom_fields = config.get("custom_fields", {})
    log_level = config.get("log_level", "INFO")
    buffer_cfg = config.get("buffer", {})
    buffer_size = int(buffer_cfg.get("max_size", config.get("buffer_size", 0)))
    logger = GovernanceLogger(
        redaction_keys=redaction_keys,
        buffer_size=buffer_size if buffer_cfg.get("enabled", bool(buffer_size)) else 0,
        custom_fields=custom_fields,
        log_level=log_level,
    )
    cloud_cfg = config.get("cloud_logging", {})
    if not cloud_cfg and _is_gcp_runtime():
        cloud_cfg = {"enabled": True}
    if cloud_cfg.get("enabled"):
        enable_cloud_logging(logger._logger, cloud_cfg)
    return logger


def _is_gcp_runtime() -> bool:
    import os

    return bool(
        os.getenv("K_SERVICE")
        or os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("GCP_PROJECT")
        or os.getenv("VERTEX_AI_AGENT_ENGINE")
    )
