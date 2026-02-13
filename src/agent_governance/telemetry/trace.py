"""Trace integration helper for OpenTelemetry/Cloud Trace."""

from __future__ import annotations

from typing import Optional


def get_trace_context() -> tuple[Optional[str], Optional[str]]:
    try:
        from opentelemetry import trace  # type: ignore

        span = trace.get_current_span()
        ctx = span.get_span_context() if span else None
        if ctx and ctx.is_valid:
            trace_id = f"{ctx.trace_id:032x}"
            span_id = f"{ctx.span_id:016x}"
            return trace_id, span_id
    except Exception:
        pass
    return None, None
