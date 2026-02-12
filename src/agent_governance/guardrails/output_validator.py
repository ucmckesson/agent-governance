from __future__ import annotations

from typing import Dict

from ..models import GuardrailAction, GuardrailResult


class OutputValidator:
    def __init__(self, config: Dict[str, object]) -> None:
        cfg = config.get("output_validation", {})
        self.max_length = int(cfg.get("max_output_length", 50000))

    def validate_length(self, output_text: str) -> GuardrailResult:
        if len(output_text) > self.max_length:
            return GuardrailResult(
                action=GuardrailAction.BLOCK,
                rule_name="max_output_length",
                reason="Output exceeds max length",
            )
        return GuardrailResult(action=GuardrailAction.ALLOW, rule_name="output_length_ok", reason="OK")
