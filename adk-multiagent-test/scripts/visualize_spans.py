from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class SpanRecord:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    timestamp: str
    duration_ms: float
    attributes: dict[str, Any]


def _parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def load_spans(path: Path) -> list[SpanRecord]:
    spans: list[SpanRecord] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                payload = obj.get("jsonPayload", {})
                spans.append(
                    SpanRecord(
                        trace_id=payload.get("trace_id", ""),
                        span_id=payload.get("span_id", ""),
                        parent_span_id=payload.get("parent_span_id"),
                        name=payload.get("name", obj.get("message", "")),
                        timestamp=payload.get("timestamp", ""),
                        duration_ms=float(payload.get("duration_ms", 0.0)),
                        attributes=payload.get("attributes", {}) or {},
                    )
                )
            except Exception:
                continue
    spans.sort(key=lambda s: _parse_iso(s.timestamp) if s.timestamp else datetime.min)
    return spans


def build_mermaid(spans: list[SpanRecord]) -> str:
    a2a = Counter()
    tool_calls = Counter()
    llm_calls = Counter()

    for s in spans:
        attrs = s.attributes
        src = attrs.get("a2a.source_agent")
        tgt = attrs.get("a2a.target_agent")
        if src and tgt:
            a2a[(src, tgt)] += 1

        agent = attrs.get("gen_ai.agent.name")
        if s.name == "call_llm" and agent:
            llm_calls[agent] += 1

        tool = attrs.get("gen_ai.tool.name")
        if tool:
            # parent agent is usually available on nearby spans; fallback unknown
            tool_calls[(attrs.get("adk_agent_name") or "agent", tool)] += 1

    lines = ["flowchart LR"]
    nodes = set()

    def _node_id(value: str) -> str:
        node = re.sub(r"[^0-9A-Za-z_]", "_", value.strip())
        if not node:
            node = "node"
        if node[0].isdigit():
            node = f"n_{node}"
        return node

    def _label(value: str) -> str:
        return value.replace('"', "'")

    def add_edge(a: str, b: str, label: str):
        na = _node_id(a)
        nb = _node_id(b)
        la = _label(a)
        lb = _label(b)
        ll = _label(label)
        nodes.add((na, la))
        nodes.add((nb, lb))
        lines.append(f"  {na}[\"{la}\"] -->|{ll}| {nb}[\"{lb}\"]")

    for (src, tgt), c in a2a.items():
        add_edge(src, tgt, f"A2A x{c}")

    for agent, c in llm_calls.items():
        add_edge(agent, "Azure OpenAI", f"LLM x{c}")

    for (_, tool), c in tool_calls.items():
        add_edge("Agent", tool, f"Tool x{c}")

    if len(lines) == 1:
        lines.append("  A[\"No communication edges found\"]")

    return "\n".join(lines)


def render_html(spans: list[SpanRecord], out: Path) -> None:
    by_trace: dict[str, list[SpanRecord]] = defaultdict(list)
    for s in spans:
        by_trace[s.trace_id].append(s)

    a2a_events = [
        s
        for s in spans
        if s.attributes.get("a2a.source_agent") and s.attributes.get("a2a.target_agent")
    ]
    tool_events = [s for s in spans if s.attributes.get("gen_ai.tool.name")]
    llm_events = [s for s in spans if s.name == "call_llm"]
    guardrails = [s for s in spans if s.attributes.get("guardrail.name")]

    mermaid = build_mermaid(spans)

    def _rows(items: list[SpanRecord], cols: list[str]) -> str:
        trs = []
        for s in items:
            vals = []
            for c in cols:
                if c == "timestamp":
                    vals.append(s.timestamp)
                elif c == "duration_ms":
                    vals.append(f"{s.duration_ms:.2f}")
                else:
                    vals.append(str(s.attributes.get(c, "")))
            trs.append("<tr>" + "".join(f"<td>{v}</td>" for v in vals) + "</tr>")
        return "\n".join(trs)

    html = f"""
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <title>ADK Span Visualization</title>
  <script type=\"module\">import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs'; mermaid.initialize({{startOnLoad:true}});</script>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; }}
    .cards {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-bottom: 16px; }}
    .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 10px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 8px; margin-bottom: 20px; }}
    th, td {{ border: 1px solid #ddd; padding: 6px; font-size: 12px; text-align: left; }}
    th {{ background: #f6f6f6; }}
    details {{ margin-bottom: 10px; }}
  </style>
</head>
<body>
  <h2>ADK + A2A + OTel Visualization</h2>
  <div class=\"cards\">
    <div class=\"card\"><b>Total spans</b><br/>{len(spans)}</div>
    <div class=\"card\"><b>Traces</b><br/>{len(by_trace)}</div>
    <div class=\"card\"><b>A2A spans</b><br/>{len(a2a_events)}</div>
    <div class=\"card\"><b>LLM spans</b><br/>{len(llm_events)}</div>
    <div class=\"card\"><b>Guardrails</b><br/>{len(guardrails)}</div>
  </div>

  <h3>Communication graph</h3>
  <div class=\"mermaid\">{mermaid}</div>

  <h3>A2A delegations</h3>
  <table>
    <thead><tr><th>timestamp</th><th>source</th><th>target</th><th>task_id</th><th>duration_ms</th></tr></thead>
    <tbody>
      {_rows(a2a_events, ["timestamp", "a2a.source_agent", "a2a.target_agent", "a2a.task_id", "duration_ms"])}
    </tbody>
  </table>

  <h3>Tool calls</h3>
  <table>
    <thead><tr><th>timestamp</th><th>tool</th><th>tool_call_id</th><th>duration_ms</th></tr></thead>
    <tbody>
      {_rows(tool_events, ["timestamp", "gen_ai.tool.name", "gen_ai.tool.call.id", "duration_ms"])}
    </tbody>
  </table>

  <h3>LLM calls</h3>
  <table>
    <thead><tr><th>timestamp</th><th>model</th><th>input_tokens</th><th>output_tokens</th><th>duration_ms</th></tr></thead>
    <tbody>
      {_rows(llm_events, ["timestamp", "gen_ai.request.model", "gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens", "duration_ms"])}
    </tbody>
  </table>

  <h3>Per-trace timeline</h3>
  {''.join(f'<details><summary>{tid} ({len(items)} spans)</summary><table><thead><tr><th>ts</th><th>span</th><th>duration_ms</th></tr></thead><tbody>' + ''.join(f'<tr><td>{s.timestamp}</td><td>{s.name}</td><td>{s.duration_ms:.2f}</td></tr>' for s in items) + '</tbody></table></details>' for tid, items in by_trace.items())}
</body>
</html>
"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize cloud logging span JSONL")
    parser.add_argument(
        "--input",
        default="artifacts/spans.cloudlogging.jsonl",
        help="Path to spans.cloudlogging.jsonl",
    )
    parser.add_argument(
        "--output",
        default="artifacts/spans_report.html",
        help="Output HTML path",
    )
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)

    spans = load_spans(in_path)
    if not spans:
        raise SystemExit(f"No spans found in {in_path}")

    render_html(spans, out_path)
    print(f"Wrote visualization: {out_path}")


if __name__ == "__main__":
    main()
