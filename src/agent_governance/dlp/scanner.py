from __future__ import annotations

import re
from typing import Dict, Iterable, List

from ..models import DLPAction, DLPFinding, DLPScanResult
from .redactor import redact_text


DEFAULT_PATTERNS = {
    "EMAIL_ADDRESS": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "PHONE_NUMBER": re.compile(r"\b\+?\d{1,3}?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "US_SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}


class DLPScanner:
    def __init__(self, action: DLPAction = DLPAction.LOG_ONLY, info_types: Iterable[str] | None = None) -> None:
        self.action = action
        self.info_types = list(info_types or DEFAULT_PATTERNS.keys())

    @classmethod
    def from_config(cls, config: Dict[str, object]) -> "DLPScanner":
        action = DLPAction(config.get("action_on_input_pii", "log"))
        info_types = config.get("info_types") or list(DEFAULT_PATTERNS.keys())
        return cls(action=action, info_types=info_types)

    def scan_text(self, text: str) -> DLPScanResult:
        findings: List[DLPFinding] = []
        for info_type in self.info_types:
            pattern = DEFAULT_PATTERNS.get(info_type)
            if not pattern:
                continue
            for match in pattern.findall(text):
                findings.append(DLPFinding(info_type=info_type, quote=match, likelihood="possible"))

        if not findings:
            return DLPScanResult(action=self.action, findings=[])

        if self.action == DLPAction.REDACT:
            redacted = redact_text(text, findings)
            return DLPScanResult(action=self.action, findings=findings, redacted_text=redacted)
        return DLPScanResult(action=self.action, findings=findings)

    def scan_and_process(self, text: str, action: DLPAction) -> tuple[str, DLPScanResult]:
        scan = self.scan_text(text)
        scan.action = action
        if action == DLPAction.BLOCK:
            return text, scan
        if action == DLPAction.REDACT and scan.redacted_text is not None:
            return scan.redacted_text, scan
        return text, scan
