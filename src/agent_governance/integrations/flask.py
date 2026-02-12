from __future__ import annotations

from typing import Callable

from ..models import EventType, RequestContext
from ..telemetry.events import build_event


def flask_middleware(app, logger, agent_identity):
    @app.before_request
    def _before():
        app.ctx = RequestContext()
        logger.emit_event(build_event(EventType.AGENT_REQUEST_START, agent_identity, app.ctx))

    @app.after_request
    def _after(response):
        ctx = getattr(app, "ctx", None)
        if ctx:
            logger.emit_event(build_event(EventType.AGENT_REQUEST_END, agent_identity, ctx))
        return response

    return app
