from __future__ import annotations

from contextlib import contextmanager
from typing import Dict, Iterator, Optional

from opentelemetry import trace


@contextmanager
def start_span(
    name: str,
    attributes: Optional[Dict[str, str]] = None,
    context=None,
) -> Iterator[trace.Span]:
    tracer = trace.get_tracer("agent_governance")
    with tracer.start_as_current_span(name, context=context) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        yield span
