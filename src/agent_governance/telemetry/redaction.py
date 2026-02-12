from __future__ import annotations

from typing import Any, Dict, Iterable

REDACTED = "[REDACTED]"


def redact_fields(payload: Dict[str, Any], keys: Iterable[str]) -> Dict[str, Any]:
    redact_keys = {k.lower() for k in keys}

    def _redact(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: (REDACTED if k.lower() in redact_keys else _redact(v)) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_redact(v) for v in obj]
        return obj

    return _redact(payload)
