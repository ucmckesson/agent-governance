from __future__ import annotations

from typing import Callable, Optional

from ..models import EventType, RequestContext
from .events import build_event
from .logger import GovernanceLogger
from .trace_context import extract_context
from .spans import start_span


class TelemetryASGIMiddleware:
    def __init__(self, app, logger: GovernanceLogger, agent_identity) -> None:
        self.app = app
        self.logger = logger
        self.agent_identity = agent_identity

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode(): v.decode() for k, v in scope.get("headers", [])}
        otel_context = extract_context(headers)
        span_ctx = start_span("agent_request", {"path": scope.get("path", "")}, context=otel_context)
        span = span_ctx.__enter__()
        context = RequestContext()
        self.logger.emit_event(build_event(EventType.AGENT_REQUEST_START, self.agent_identity, context))

        async def send_wrapper(message):
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            self.logger.emit_event(build_event(EventType.AGENT_REQUEST_END, self.agent_identity, context))
            span_ctx.__exit__(None, None, None)
