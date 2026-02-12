from __future__ import annotations

from ..models import ComplianceCheckResult, ComplianceStatus


def compliant(name: str, message: str) -> ComplianceCheckResult:
    return ComplianceCheckResult(name=name, status=ComplianceStatus.COMPLIANT, message=message)


def non_compliant(name: str, message: str) -> ComplianceCheckResult:
    return ComplianceCheckResult(name=name, status=ComplianceStatus.NON_COMPLIANT, message=message)


def review_needed(name: str, message: str) -> ComplianceCheckResult:
    return ComplianceCheckResult(name=name, status=ComplianceStatus.REVIEW_NEEDED, message=message)
