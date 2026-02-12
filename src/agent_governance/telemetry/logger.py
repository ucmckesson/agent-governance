from __future__ import annotations

import json
import logging
import sys
from typing import Any, Dict, Iterable, Optional

from ..exceptions import TelemetryError
from ..models import BaseEvent
from .buffered_emitter import BufferedEmitter
from .redaction import redact_fields


class GovernanceLogger:
    """Structured JSON logger with optional buffering."""

    def __init__(
        self,
        name: str = "agent_governance",
        redaction_keys: Optional[Iterable[str]] = None,
        buffer_size: int = 0,
    ) -> None:
        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        self._logger.handlers = [handler]
        self._redaction_keys = set(redaction_keys or [])
        self._emitter = BufferedEmitter(self._emit, buffer_size) if buffer_size > 0 else None

    def emit_event(self, event: BaseEvent) -> None:
        try:
            payload = event.model_dump(mode="json")
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


def init_telemetry(config: Dict[str, Any]) -> GovernanceLogger:
    redaction_keys = config.get("redaction_keys", [])
    buffer_size = int(config.get("buffer_size", 0))
    return GovernanceLogger(redaction_keys=redaction_keys, buffer_size=buffer_size)
