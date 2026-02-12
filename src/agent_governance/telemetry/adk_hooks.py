"""Minimal ADK hook placeholders."""

from __future__ import annotations

from ..models import EventType, RequestContext
from .events import build_event
from .logger import GovernanceLogger


def on_agent_start(logger: GovernanceLogger, agent_identity, context: RequestContext) -> None:
    logger.emit_event(build_event(EventType.AGENT_REQUEST_START, agent_identity, context))


def on_agent_end(logger: GovernanceLogger, agent_identity, context: RequestContext) -> None:
    logger.emit_event(build_event(EventType.AGENT_REQUEST_END, agent_identity, context))
