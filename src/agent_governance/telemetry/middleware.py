from __future__ import annotations

from typing import Callable, Optional

from ..models import EventType, RequestContext
from .events import build_event
from .logger import GovernanceLogger


class TelemetryASGIMiddleware:
    def __init__(self, app, logger: GovernanceLogger, agent_identity) -> None:
        self.app = app
        self.logger = logger
        self.agent_identity = agent_identity

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        context = RequestContext()
        self.logger.emit_event(build_event(EventType.AGENT_REQUEST_START, self.agent_identity, context))

        async def send_wrapper(message):
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            self.logger.emit_event(build_event(EventType.AGENT_REQUEST_END, self.agent_identity, context))
