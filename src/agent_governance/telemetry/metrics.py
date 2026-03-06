from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


@dataclass
class ToolStats:
    calls: int = 0
    errors: int = 0
    latency_ms: List[int] = field(default_factory=list)


class AgentMetricsTracker:
    """In-process runtime metrics aggregation for agent health analytics."""

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", True))
        self._request_latencies: List[int] = []
        self._requests_total = 0
        self._errors_total = 0
        self._delegations_total = 0
        self._cost_usd_total = 0.0
        self._input_tokens_total = 0
        self._output_tokens_total = 0
        self._tool_stats: Dict[str, ToolStats] = {}
        self._delegation_edges: Dict[Tuple[str, str], int] = {}

    def record_request_end(self, status: str, latency_ms: int) -> None:
        if not self.enabled:
            return
        self._requests_total += 1
        self._request_latencies.append(max(0, int(latency_ms)))
        if status != "success":
            self._errors_total += 1

    def record_tool_call_end(self, tool_name: str, status: str, latency_ms: int) -> None:
        if not self.enabled:
            return
        stats = self._tool_stats.setdefault(tool_name, ToolStats())
        stats.calls += 1
        stats.latency_ms.append(max(0, int(latency_ms)))
        if status != "success":
            stats.errors += 1

    def record_delegation(self, source_agent: str, target_agent: str) -> None:
        if not self.enabled:
            return
        self._delegations_total += 1
        key = (source_agent, target_agent)
        self._delegation_edges[key] = self._delegation_edges.get(key, 0) + 1

    def record_cost(self, estimated_usd: float, input_tokens: int, output_tokens: int) -> None:
        if not self.enabled:
            return
        self._cost_usd_total += max(0.0, float(estimated_usd))
        self._input_tokens_total += max(0, int(input_tokens))
        self._output_tokens_total += max(0, int(output_tokens))

    def snapshot(self) -> Dict[str, Any]:
        if not self.enabled:
            return {}

        tool_analytics: Dict[str, Any] = {}
        for tool_name, stats in self._tool_stats.items():
            p95 = _percentile(stats.latency_ms, 95.0)
            tool_analytics[tool_name] = {
                "calls": stats.calls,
                "errors": stats.errors,
                "error_rate": round((stats.errors / stats.calls), 4) if stats.calls else 0.0,
                "p95_latency_ms": p95,
            }

        return {
            "requests_total": self._requests_total,
            "errors_total": self._errors_total,
            "error_rate": round((self._errors_total / self._requests_total), 4) if self._requests_total else 0.0,
            "request_p95_latency_ms": _percentile(self._request_latencies, 95.0),
            "delegations_total": self._delegations_total,
            "cost_usd_total": round(self._cost_usd_total, 8),
            "input_tokens_total": self._input_tokens_total,
            "output_tokens_total": self._output_tokens_total,
            "tool_analytics": tool_analytics,
            "delegation_edges": [
                {"source_agent": src, "target_agent": dst, "count": count}
                for (src, dst), count in sorted(self._delegation_edges.items(), key=lambda item: item[1], reverse=True)
            ],
        }


def _percentile(values: List[int], percentile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    idx = int(round(((percentile / 100.0) * (len(ordered) - 1))))
    idx = max(0, min(idx, len(ordered) - 1))
    return int(ordered[idx])
