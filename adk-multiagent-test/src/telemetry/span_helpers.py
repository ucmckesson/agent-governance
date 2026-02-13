from __future__ import annotations

from contextlib import contextmanager
from opentelemetry import trace


@contextmanager
def guardrail_span(name: str, guardrail_type: str):
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span(f"guardrail.{name}") as span:
        span.set_attribute("guardrail.name", name)
        span.set_attribute("guardrail.type", guardrail_type)
        yield span
