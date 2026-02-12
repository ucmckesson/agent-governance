from __future__ import annotations

import json
from typing import Any, Dict

from ..models import EvalRunResult


def to_json(result: EvalRunResult) -> str:
    return json.dumps(result.model_dump(mode="json"), indent=2)


def to_markdown(result: EvalRunResult) -> str:
    rows = "\n".join(
        f"| {m.name} | {m.value:.4f} | {m.verdict.value} | {m.threshold or '-'} |" for m in result.metrics
    )
    return (
        "| Metric | Value | Verdict | Threshold |\n"
        "|---|---|---|---|\n"
        f"{rows}\n\n"
        f"**Overall:** {result.overall.value}"
    )
