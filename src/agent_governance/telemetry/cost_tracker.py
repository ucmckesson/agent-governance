from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class CostUsage:
    model: str
    input_tokens: int
    output_tokens: int
    estimated_usd: float


class CostTracker:
    """Runtime cost tracker for request/session-level estimates."""

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", False))
        self._pricing = cfg.get("pricing", {}) or {}
        self._threshold = float(cfg.get("alert_threshold_usd", 0) or 0)
        self._request_totals: Dict[str, float] = {}
        self._session_totals: Dict[str, float] = {}

    @property
    def threshold_usd(self) -> float:
        return self._threshold

    def estimate(self, model: str, input_tokens: int, output_tokens: int) -> CostUsage:
        prices = self._pricing.get(model, {}) or {}
        input_price = float(prices.get("input", 0) or 0)
        output_price = float(prices.get("output", 0) or 0)
        estimated = (max(0, input_tokens) / 1_000_000.0) * input_price + (max(0, output_tokens) / 1_000_000.0) * output_price
        return CostUsage(
            model=model,
            input_tokens=max(0, int(input_tokens)),
            output_tokens=max(0, int(output_tokens)),
            estimated_usd=round(estimated, 8),
        )

    def record(self, request_id: str, session_id: str | None, usage: CostUsage) -> Dict[str, float]:
        req_total = self._request_totals.get(request_id, 0.0) + usage.estimated_usd
        self._request_totals[request_id] = req_total

        sess_total = 0.0
        if session_id:
            sess_total = self._session_totals.get(session_id, 0.0) + usage.estimated_usd
            self._session_totals[session_id] = sess_total

        return {
            "request_total_usd": round(req_total, 8),
            "session_total_usd": round(sess_total, 8),
        }

    def finalize_request(self, request_id: str) -> float:
        return round(self._request_totals.pop(request_id, 0.0), 8)
