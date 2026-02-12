from __future__ import annotations

from ..telemetry.middleware import TelemetryASGIMiddleware


def cloud_run_middleware(app, logger, agent_identity):
    return TelemetryASGIMiddleware(app, logger, agent_identity)
