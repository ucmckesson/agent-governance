from __future__ import annotations

import re
from typing import Dict, Iterable, List

from ..models import DLPAction, DLPFinding, DLPScanResult
from .redactor import redact_text


DEFAULT_PATTERNS = {
    "EMAIL_ADDRESS": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "PHONE_NUMBER": re.compile(r"\b\+?\d{1,3}?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "US_SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "CREDIT_CARD_NUMBER": re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    "PERSON_NAME": re.compile(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b"),
    "ADDRESS": re.compile(r"\b\d{1,5}\s+\w+(?:\s+\w+)*\s+(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Lane|Ln|Dr|Drive|Ct|Court)\b", re.IGNORECASE),
}

MODEL_ARMOR_PATTERNS = {
    "EMAIL_ADDRESS": DEFAULT_PATTERNS["EMAIL_ADDRESS"],
    "PHONE_NUMBER": DEFAULT_PATTERNS["PHONE_NUMBER"],
    "US_SSN": DEFAULT_PATTERNS["US_SSN"],
    "CREDIT_CARD_NUMBER": DEFAULT_PATTERNS["CREDIT_CARD_NUMBER"],
}

INFO_TYPE_ALIASES = {
    "SSN": "US_SSN",
    "CREDIT_CARD": "CREDIT_CARD_NUMBER",
    "NAME": "PERSON_NAME",
    "PERSONAL_ADDRESS": "ADDRESS",
}


class DLPScanner:
    def __init__(
        self,
        action: DLPAction = DLPAction.LOG_ONLY,
        info_types: Iterable[str] | None = None,
        provider: str = "sensitive_data_protection",
    ) -> None:
        self.action = action
        self.provider = provider
        patterns = MODEL_ARMOR_PATTERNS if provider == "model_armor" else DEFAULT_PATTERNS
        self.info_types = list(info_types or patterns.keys())

    @classmethod
    def from_config(cls, config: Dict[str, object]) -> "DLPScanner":
        action = DLPAction(config.get("action_on_input_pii", "log"))
        provider = str(config.get("provider", "sensitive_data_protection") or "sensitive_data_protection").lower()
        patterns = MODEL_ARMOR_PATTERNS if provider == "model_armor" else DEFAULT_PATTERNS
        info_types = config.get("info_types") or list(patterns.keys())
        return cls(action=action, info_types=info_types, provider=provider)

    def scan_text(self, text: str) -> DLPScanResult:
        findings: List[DLPFinding] = []
        patterns = MODEL_ARMOR_PATTERNS if self.provider == "model_armor" else DEFAULT_PATTERNS
        for info_type in self.info_types:
            normalized = INFO_TYPE_ALIASES.get(info_type, info_type)
            pattern = patterns.get(normalized)
            if not pattern:
                continue
            for match in pattern.findall(text):
                findings.append(DLPFinding(info_type=normalized, quote=match, likelihood="possible"))

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
        if action == DLPAction.REDACT:
            if scan.redacted_text is None and scan.findings:
                scan.redacted_text = redact_text(text, scan.findings)
            if scan.redacted_text is not None:
                return scan.redacted_text, scan
        return text, scan
