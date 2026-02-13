from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _iso8601_nanos(ns: int) -> str:
    dt = datetime.fromtimestamp(ns / 1_000_000_000, tz=timezone.utc)
    return dt.isoformat()


def _trace_id_hex(trace_id: int) -> str:
    return f"{trace_id:032x}"


def _span_id_hex(span_id: int) -> str:
    return f"{span_id:016x}"


def format_span_record(span) -> dict[str, Any]:
    duration_ms = max(0.0, (span.end_time - span.start_time) / 1_000_000)
    record: dict[str, Any] = {
        "timestamp": _iso8601_nanos(span.start_time),
        "name": span.name,
        "trace_id": _trace_id_hex(span.context.trace_id),
        "span_id": _span_id_hex(span.context.span_id),
        "parent_span_id": _span_id_hex(span.parent.span_id) if span.parent else None,
        "duration_ms": round(duration_ms, 3),
        "status_code": getattr(span.status.status_code, "name", str(span.status.status_code)),
        "attributes": dict(span.attributes or {}),
    }
    return record


def spans_to_cloud_logging_entries(spans, project_id: str | None = None) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for span in spans:
        rec = format_span_record(span)
        trace_id = rec["trace_id"]
        span_id = rec["span_id"]
        cloud_trace = (
            f"projects/{project_id}/traces/{trace_id}"
            if project_id
            else trace_id
        )
        entries.append(
            {
                "severity": "INFO",
                "message": rec["name"],
                "logging.googleapis.com/trace": cloud_trace,
                "logging.googleapis.com/spanId": span_id,
                "logging.googleapis.com/trace_sampled": True,
                "jsonPayload": rec,
            }
        )
    return entries


def summarize_spans(spans) -> dict[str, Any]:
    total = len(spans)
    by_name: dict[str, int] = {}
    a2a = 0
    guardrails = 0
    llm = 0
    tools = 0

    for span in spans:
        by_name[span.name] = by_name.get(span.name, 0) + 1
        attrs = span.attributes or {}
        if attrs.get("a2a.target_agent"):
            a2a += 1
        if attrs.get("guardrail.name"):
            guardrails += 1
        if span.name == "call_llm" or attrs.get("llm.provider"):
            llm += 1
        if attrs.get("gen_ai.tool.name"):
            tools += 1

    return {
        "total_spans": total,
        "a2a_spans": a2a,
        "guardrail_spans": guardrails,
        "llm_spans": llm,
        "tool_spans": tools,
        "top_span_names": dict(sorted(by_name.items(), key=lambda x: x[1], reverse=True)[:10]),
    }
