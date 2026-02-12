from __future__ import annotations

from typing import Any, Dict


class OutputValidator:
    def __init__(self, max_length: int = 20000) -> None:
        self.max_length = max_length

    def validate(self, output: Dict[str, Any]) -> tuple[bool, str]:
        text = str(output)
        if len(text) > self.max_length:
            return False, "output_too_large"
        return True, "ok"
