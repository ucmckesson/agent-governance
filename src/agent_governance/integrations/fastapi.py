from __future__ import annotations

from ..telemetry.middleware import TelemetryASGIMiddleware


def fastapi_middleware(app, logger, agent_identity):
    app.add_middleware(TelemetryASGIMiddleware, logger=logger, agent_identity=agent_identity)
    return app
