from __future__ import annotations

from typing import Any, Dict

from ..telemetry import GovernanceLogger
from ..telemetry.adk_hooks import on_agent_end, on_agent_start
from ..models import RequestContext


def attach_adk_hooks(logger: GovernanceLogger, agent_identity) -> Dict[str, Any]:
    """Return hook callbacks for ADK lifecycle integration."""
    def _on_start():
        on_agent_start(logger, agent_identity, RequestContext())

    def _on_end():
        on_agent_end(logger, agent_identity, RequestContext())

    return {"on_start": _on_start, "on_end": _on_end}
