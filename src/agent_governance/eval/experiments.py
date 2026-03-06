from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from ..models import EvalRunResult


@dataclass
class Experiment:
    name: str
    dataset_name: str
    config_overrides: Dict[str, object] = field(default_factory=dict)
    results: List[EvalRunResult] = field(default_factory=list)

    def metric_averages(self) -> Dict[str, float]:
        totals: Dict[str, float] = {}
        counts: Dict[str, int] = {}
        for run in self.results:
            for metric in run.metrics:
                totals[metric.name] = totals.get(metric.name, 0.0) + float(metric.value)
                counts[metric.name] = counts.get(metric.name, 0) + 1
        return {
            name: round((totals[name] / counts[name]), 6)
            for name in totals
            if counts.get(name, 0) > 0
        }


@dataclass
class ComparisonReport:
    baseline: str
    candidate: str
    deltas: Dict[str, float]
    improved_metrics: List[str]
    regressed_metrics: List[str]


class ExperimentComparison:
    def __init__(self, baseline: Experiment, candidate: Experiment) -> None:
        self.baseline = baseline
        self.candidate = candidate

    def compare(self) -> ComparisonReport:
        base = self.baseline.metric_averages()
        cand = self.candidate.metric_averages()
        keys = sorted(set(base.keys()) | set(cand.keys()))

        deltas: Dict[str, float] = {}
        improved: List[str] = []
        regressed: List[str] = []

        for key in keys:
            base_value = base.get(key, 0.0)
            cand_value = cand.get(key, 0.0)
            delta = round(cand_value - base_value, 6)
            deltas[key] = delta
            if delta > 0:
                improved.append(key)
            elif delta < 0:
                regressed.append(key)

        return ComparisonReport(
            baseline=self.baseline.name,
            candidate=self.candidate.name,
            deltas=deltas,
            improved_metrics=improved,
            regressed_metrics=regressed,
        )
