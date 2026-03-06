from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from ..golden_data.loader import GoldenDataset


class Annotation(BaseModel):
    trace_id: str
    span_id: Optional[str] = None
    label: str
    score: Optional[float] = None
    note: Optional[str] = None
    annotator: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class JsonlAnnotationStore:
    """Simple JSONL-backed annotation store.

    This backend is intentionally lightweight and works in local/CI environments.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text("")

    def save(self, annotation: Annotation) -> None:
        line = json.dumps(annotation.model_dump(mode="json"), separators=(",", ":"))
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def query(self, trace_id: str | None = None) -> List[Annotation]:
        items: List[Annotation] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = Annotation.model_validate(json.loads(line))
            if trace_id is None or item.trace_id == trace_id:
                items.append(item)
        return items


class AnnotationClient:
    def __init__(self, store: JsonlAnnotationStore) -> None:
        self._store = store

    async def annotate(self, annotation: Annotation) -> None:
        self._store.save(annotation)

    async def get_annotations(self, trace_id: str) -> List[Annotation]:
        return self._store.query(trace_id=trace_id)

    async def export_annotated_traces(
        self,
        label_filter: str,
        date_range: tuple[datetime, datetime] | None = None,
    ) -> GoldenDataset:
        start: datetime | None = None
        end: datetime | None = None
        if date_range is not None:
            start, end = date_range

        items: List[Dict[str, object]] = []
        for annotation in self._store.query():
            if annotation.label != label_filter:
                continue
            if start is not None and annotation.timestamp < start:
                continue
            if end is not None and annotation.timestamp > end:
                continue
            items.append(
                {
                    "trace_id": annotation.trace_id,
                    "span_id": annotation.span_id,
                    "label": annotation.label,
                    "score": annotation.score,
                    "note": annotation.note,
                    "annotator": annotation.annotator,
                    "timestamp": annotation.timestamp.isoformat(),
                }
            )

        return GoldenDataset.from_inline(items)
