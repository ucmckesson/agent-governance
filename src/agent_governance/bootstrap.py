from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .config import GovernanceConfig, load_config
from .integrations.adk import GovernanceADKMiddleware
from .registry import AgentLifecycleManager
from .runtime import RuntimeMetadata, detect_runtime
from .telemetry import GovernanceLogger, init_telemetry


@dataclass
class GovernanceRuntime:
    config: GovernanceConfig
    runtime: RuntimeMetadata
    logger: GovernanceLogger
    middleware: GovernanceADKMiddleware
    lifecycle: AgentLifecycleManager


def init_governance(
    config_path: str | None = None,
    *,
    auto_register: bool = True,
    start_heartbeat: bool = True,
) -> GovernanceRuntime:
    """One-call initialization for production deployments.

    Initializes config, logger, ADK middleware, runtime detection, and
    lifecycle registration/heartbeat.
    """
    cfg = load_config(config_path)
    runtime = detect_runtime()

    # enrich agent metadata if runtime provides better values
    if runtime.project_id and not cfg.agent.gcp_project:
        cfg.agent.gcp_project = runtime.project_id
    if runtime.region and (not cfg.agent.region or cfg.agent.region == "us-central1"):
        cfg.agent.region = runtime.region

    logger = init_telemetry(cfg.section("telemetry"))
    middleware = GovernanceADKMiddleware(cfg)
    lifecycle = AgentLifecycleManager(cfg.agent, cfg.section("registry"), logger, runtime)

    if auto_register:
        lifecycle.register_startup()
    if start_heartbeat:
        lifecycle.start_heartbeat()

    return GovernanceRuntime(
        config=cfg,
        runtime=runtime,
        logger=logger,
        middleware=middleware,
        lifecycle=lifecycle,
    )
