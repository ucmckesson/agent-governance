from __future__ import annotations

from typing import Dict, Optional

from ..models import EvalVerdict


class Thresholds:
    def __init__(self, thresholds: Dict[str, float]) -> None:
        self._thresholds = thresholds

    def get(self, name: str) -> Optional[float]:
        return self._thresholds.get(name)

    def evaluate(self, name: str, value: float) -> EvalVerdict:
        threshold = self._thresholds.get(name)
        if threshold is None:
            return EvalVerdict.SKIP
        if value >= threshold:
            return EvalVerdict.PASS
        if value >= threshold * 0.95:
            return EvalVerdict.WARNING
        return EvalVerdict.FAIL
