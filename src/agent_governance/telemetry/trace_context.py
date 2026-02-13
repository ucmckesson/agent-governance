from __future__ import annotations

from typing import Dict


def extract_context(headers: Dict[str, str]):
    try:
        from opentelemetry.propagate import extract

        return extract(headers)
    except Exception:
        return None
