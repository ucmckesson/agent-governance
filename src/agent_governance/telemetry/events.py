from __future__ import annotations

from typing import Any, Dict

from ..models import AgentIdentity, BaseEvent, EventType, RequestContext


def build_event(
    event_type: EventType,
    agent: AgentIdentity,
    context: RequestContext,
    attributes: Dict[str, Any] | None = None,
) -> BaseEvent:
    return BaseEvent(
        event_type=event_type,
        agent=agent,
        context=context,
        attributes=attributes or {},
    )
