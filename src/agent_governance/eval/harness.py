from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List

from ..exceptions import EvalError
from ..models import EvalMetricResult, EvalRunResult, EvalVerdict
from .thresholds import Thresholds


class EvalHarness:
    def __init__(self, thresholds: Dict[str, float] | None = None) -> None:
        self.thresholds = Thresholds(thresholds or {})

    def run(
        self,
        agent_id: str,
        metrics: Iterable[Callable[[], float]],
        metric_names: Iterable[str],
    ) -> EvalRunResult:
        started = datetime.now(timezone.utc)
        results: List[EvalMetricResult] = []
        overall = EvalVerdict.PASS
        try:
            for name, fn in zip(metric_names, metrics):
                value = fn()
                threshold = self.thresholds.get(name)
                verdict = self.thresholds.evaluate(name, value)
                if verdict in {EvalVerdict.FAIL, EvalVerdict.WARNING}:
                    overall = verdict if overall != EvalVerdict.FAIL else overall
                results.append(
                    EvalMetricResult(name=name, value=value, verdict=verdict, threshold=threshold)
                )
        except Exception as exc:
            raise EvalError(str(exc)) from exc
        finished = datetime.now(timezone.utc)
        return EvalRunResult(
            agent_id=agent_id,
            started_at=started,
            finished_at=finished,
            metrics=results,
            overall=overall,
        )
