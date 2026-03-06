from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from ..models import EventType
from .loader import GoldenDataset
from .versioner import dataset_hash


class TraceCapture:
    """Capture production telemetry events and convert them into golden datasets."""

    def __init__(self, events_path: str | Path | None = None, events: Iterable[Dict[str, Any]] | None = None) -> None:
        self._events_path = Path(events_path) if events_path else None
        self._events = list(events or [])
        self._annotations: Dict[str, List[str]] = {}

    async def capture_from_cloud_trace(
        self,
        agent_id: str,
        filters: Dict[str, Any] | None = None,
        sample_size: int = 100,
    ) -> GoldenDataset:
        records = self._load_events()
        filters = filters or {}
        filtered: List[Dict[str, Any]] = []
        for record in records:
            if str(record.get("agent", {}).get("agent_id", "")) != agent_id:
                continue
            event_type = str(record.get("event_type", ""))
            if filters.get("event_type") and event_type != str(filters["event_type"]):
                continue
            if filters.get("status") and str(record.get("attributes", {}).get("status", "")) != str(filters["status"]):
                continue
            if event_type != EventType.AGENT_REQUEST_END.value:
                continue
            filtered.append(record)

        items = [self._to_dataset_case(record) for record in filtered[: max(0, int(sample_size))]]
        return GoldenDataset.from_inline(items)

    async def capture_from_session(self, session_id: str) -> GoldenDataset:
        records = self._load_events()
        session_records = [
            record
            for record in records
            if str(record.get("context", {}).get("session_id", "")) == session_id
            and str(record.get("event_type", "")) == EventType.AGENT_REQUEST_END.value
        ]
        items = [self._to_dataset_case(record) for record in session_records]
        return GoldenDataset.from_inline(items)

    async def capture_on_annotation(self, trace_id: str, annotation: str) -> None:
        labels = self._annotations.setdefault(trace_id, [])
        labels.append(annotation)

    def _load_events(self) -> List[Dict[str, Any]]:
        if self._events:
            return list(self._events)
        if self._events_path is None or not self._events_path.exists():
            return []

        items: List[Dict[str, Any]] = []
        for line in self._events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                continue
        return items

    def _to_dataset_case(self, event: Dict[str, Any]) -> Dict[str, Any]:
        attrs = event.get("attributes", {}) or {}
        ctx = event.get("context", {}) or {}
        prompt = attrs.get("prompt") or attrs.get("input") or ""
        expected = attrs.get("output") or attrs.get("expected") or ""

        case = {
            "prompt": prompt,
            "expected": expected,
            "trace_id": ctx.get("trace_id"),
            "request_id": ctx.get("request_id"),
            "session_id": ctx.get("session_id"),
            "status": attrs.get("status"),
            "latency_ms": attrs.get("latency_ms"),
            "agent_id": event.get("agent", {}).get("agent_id"),
            "event_type": event.get("event_type"),
        }
        case["dataset_version"] = dataset_hash([case])
        return case
