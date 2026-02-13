from __future__ import annotations

from ..bootstrap import GovernanceRuntime, init_governance
from ..telemetry.middleware import TelemetryASGIMiddleware
from .fastapi import fastapi_middleware


def cloud_run_middleware(app, logger, agent_identity):
    return TelemetryASGIMiddleware(app, logger, agent_identity)


def cloud_run_fastapi_runtime(app, config_path: str = "governance.yaml") -> GovernanceRuntime:
    """Bootstrap governance + middleware + lifecycle hooks for FastAPI on Cloud Run.

    Returns the initialized `GovernanceRuntime` so callers can access logger,
    middleware and lifecycle manager.
    """
    runtime = init_governance(config_path, auto_register=True, start_heartbeat=True)
    fastapi_middleware(app, runtime.logger, runtime.config.agent)

    if hasattr(app, "add_event_handler"):
        app.add_event_handler("shutdown", runtime.lifecycle.mark_stopped)
        app.add_event_handler("shutdown", runtime.lifecycle.stop_heartbeat)

    return runtime
