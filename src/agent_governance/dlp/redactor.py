from __future__ import annotations

from typing import Iterable

from ..models import DLPFinding

REDACTION_TOKEN = "[REDACTED]"


def redact_text(text: str, findings: Iterable[DLPFinding]) -> str:
    redacted = text
    for finding in findings:
        if finding.quote:
            redacted = redacted.replace(finding.quote, REDACTION_TOKEN)
    return redacted
