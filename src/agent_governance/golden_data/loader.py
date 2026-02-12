from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from ..exceptions import EvalError


class GoldenDataset:
    def __init__(self, items: List[Dict[str, Any]]) -> None:
        self.items = items

    @classmethod
    def from_jsonl(cls, path: str | Path) -> "GoldenDataset":
        try:
            items: List[Dict[str, Any]] = []
            for line in Path(path).read_text().splitlines():
                if line.strip():
                    items.append(json.loads(line))
            return cls(items)
        except Exception as exc:
            raise EvalError(str(exc)) from exc

    @classmethod
    def from_inline(cls, items: Iterable[Dict[str, Any]]) -> "GoldenDataset":
        return cls(list(items))
