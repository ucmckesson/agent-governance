from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from ..models import GuardrailAction, GuardrailResult


class InputValidator:
    def __init__(self, config: Dict[str, object]) -> None:
        cfg = config.get("input_validation", {})
        self.max_length = int(cfg.get("max_input_length", 10000))
        self.max_tokens = int(cfg.get("max_input_tokens", 4096))
        self.block_injection = bool(cfg.get("block_known_injection_patterns", True))
        self.patterns = self._load_patterns(cfg.get("injection_patterns_file"))

    @staticmethod
    def _load_patterns(path: object) -> List[str]:
        if not path:
            return []
        return [line.strip() for line in Path(str(path)).read_text().splitlines() if line.strip()]

    def validate(self, input_text: str) -> GuardrailResult:
        if len(input_text) > self.max_length:
            return GuardrailResult(
                action=GuardrailAction.BLOCK,
                rule_name="max_input_length",
                reason="Input exceeds max length",
            )
        if self._token_count(input_text) > self.max_tokens:
            return GuardrailResult(
                action=GuardrailAction.BLOCK,
                rule_name="max_input_tokens",
                reason="Input exceeds max token count",
            )
        return GuardrailResult(action=GuardrailAction.ALLOW, rule_name="input_length_ok", reason="OK")

    def check_injection(self, input_text: str) -> GuardrailResult:
        if not self.block_injection or not self.patterns:
            return GuardrailResult(action=GuardrailAction.ALLOW, rule_name="injection_disabled", reason="OK")
        lower = input_text.lower()
        for pattern in self.patterns:
            if pattern.lower() in lower:
                return GuardrailResult(
                    action=GuardrailAction.BLOCK,
                    rule_name="injection_pattern",
                    reason="Input matches injection pattern",
                    details={"pattern": pattern},
                )
        return GuardrailResult(action=GuardrailAction.ALLOW, rule_name="no_injection", reason="OK")

    @staticmethod
    def _token_count(text: str) -> int:
        return len(text.split())
