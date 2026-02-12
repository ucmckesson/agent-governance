from __future__ import annotations

from typing import Dict, Iterable, List


def validate_schema(items: Iterable[Dict[str, object]], required_keys: List[str]) -> tuple[bool, list[str]]:
    missing_any: list[str] = []
    for idx, item in enumerate(items):
        for key in required_keys:
            if key not in item:
                missing_any.append(f"{idx}:{key}")
    return len(missing_any) == 0, missing_any
