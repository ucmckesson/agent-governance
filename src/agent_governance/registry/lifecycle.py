from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..models import EventType, RequestContext
from ..telemetry.events import build_event
from ..telemetry.logger import GovernanceLogger
from ..runtime import RuntimeMetadata
from .bq_writer import write_registration
from .models import AgentRegistrationRecord


class AgentLifecycleManager:
    """Handles registration + heartbeat lifecycle events for deployed agents."""

    def __init__(
        self,
        agent,
        registry_cfg: Dict[str, Any],
        logger: GovernanceLogger,
        runtime: RuntimeMetadata,
    ) -> None:
        self._agent = agent
        self._cfg = registry_cfg or {}
        self._logger = logger
        self._runtime = runtime
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def register_startup(self) -> None:
        self._write_registration("started")
        self._emit_status("started")

    def mark_unhealthy(self, reason: str | None = None) -> None:
        self._write_registration("unhealthy")
        self._emit_status("unhealthy", reason=reason)

    def mark_stopped(self) -> None:
        self._write_registration("stopped")
        self._emit_status("stopped")

    def start_heartbeat(self, interval_s: int | None = None) -> None:
        interval = interval_s or int(self._cfg.get("heartbeat_interval_s", 60))
        if self._thread and self._thread.is_alive():
            return

        self._stop.clear()

        def _loop() -> None:
            while not self._stop.wait(interval):
                self._write_registration("healthy")
                self._emit_status("healthy")

        self._thread = threading.Thread(target=_loop, daemon=True, name="agent-governance-heartbeat")
        self._thread.start()

    def stop_heartbeat(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _write_registration(self, status: str) -> None:
        project = self._cfg.get("bq_project")
        dataset = self._cfg.get("bq_dataset")
        table = self._cfg.get("bq_table")
        if not (project and dataset and table):
            return

        record = AgentRegistrationRecord(
            agent_id=self._agent.agent_id,
            env=self._agent.env.value if hasattr(self._agent.env, "value") else str(self._agent.env),
            runtime=self._runtime.platform,
            service_name=self._runtime.service_name,
            region=self._runtime.region or self._agent.region,
            cloud_run_url=self._runtime.service_url,
            revision=self._runtime.revision,
            version=self._agent.version,
            owner=self._cfg.get("owner"),
            status=status,
            last_deploy_times=[datetime.now(timezone.utc)],
        )
        try:
            write_registration(record, project=project, dataset=dataset, table=table)
        except Exception as exc:
            self._emit_status("registration_error", reason=str(exc))

    def _emit_status(self, status: str, reason: str | None = None) -> None:
        ctx = RequestContext()
        attrs: Dict[str, Any] = {
            "status": status,
            "runtime": self._runtime.platform,
            "service_name": self._runtime.service_name,
            "revision": self._runtime.revision,
        }
        if reason:
            attrs["reason"] = reason
        self._logger.emit_event(build_event(EventType.REGISTRATION_EVENT, self._agent, ctx, attrs))
