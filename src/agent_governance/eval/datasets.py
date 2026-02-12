from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from ..exceptions import EvalError


def load_jsonl(path: str | Path) -> List[Dict[str, Any]]:
    try:
        items: List[Dict[str, Any]] = []
        for line in Path(path).read_text().splitlines():
            if line.strip():
                items.append(json.loads(line))
        return items
    except Exception as exc:
        raise EvalError(str(exc)) from exc
