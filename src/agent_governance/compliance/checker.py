from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List

from ..models import ComplianceCheckResult, ComplianceReport, ComplianceStatus
from .checks import (
    attestation_check,
    data_class_check,
    eval_check,
    iam_check,
    label_check,
    registry_check,
    scc_check,
)


class ComplianceChecker:
    def __init__(self, checks: Iterable = None) -> None:
        self.checks = list(checks or [
            registry_check,
            label_check,
            eval_check,
            scc_check,
            iam_check,
            attestation_check,
            data_class_check,
        ])

    def run(self, agent_id: str) -> ComplianceReport:
        results: List[ComplianceCheckResult] = []
        overall = ComplianceStatus.COMPLIANT
        for check in self.checks:
            result = check(agent_id)
            results.append(result)
            if result.status == ComplianceStatus.NON_COMPLIANT:
                overall = ComplianceStatus.NON_COMPLIANT
            elif result.status == ComplianceStatus.REVIEW_NEEDED and overall != ComplianceStatus.NON_COMPLIANT:
                overall = ComplianceStatus.REVIEW_NEEDED
        return ComplianceReport(
            agent_id=agent_id,
            generated_at=datetime.now(timezone.utc),
            status=overall,
            checks=results,
        )
