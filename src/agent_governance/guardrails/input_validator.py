from __future__ import annotations

from typing import Any, Dict


class InputValidator:
    def __init__(self, max_length: int = 10000) -> None:
        self.max_length = max_length

    def validate(self, payload: Dict[str, Any]) -> tuple[bool, str]:
        text = str(payload)
        if len(text) > self.max_length:
            return False, "input_too_large"
        return True, "ok"
