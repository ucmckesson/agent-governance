from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SDK_SRC = PROJECT_ROOT.parent / "src"
if str(SDK_SRC) not in sys.path:
    sys.path.insert(0, str(SDK_SRC))

from google.adk.runners import InMemoryRunner
from google.genai import types

from src.agents.orchestrator import INSTRUCTION, build_orchestrator
from src.config import get_settings
from src.telemetry.setup import setup_telemetry
from src.telemetry.span_formatter import spans_to_cloud_logging_entries

from agent_governance import init_governance
from agent_governance.dlp import DLPScanner
from agent_governance.eval import Experiment, ExperimentComparison
from agent_governance.golden_data import TraceCapture
from agent_governance.models import EvalMetricResult, EvalRunResult, EvalVerdict
from agent_governance.telemetry import Annotation, AnnotationClient, JsonlAnnotationStore

ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
JSON_REPORT = ARTIFACTS_DIR / "feature_matrix_report.json"
MD_REPORT = ARTIFACTS_DIR / "feature_matrix_report.md"


@dataclass
class FeatureCheck:
    name: str
    passed: bool
    details: str


@dataclass
class ScenarioResult:
    query: str
    session_id: str
    output: str
    transfers: list[str]
    request_id: str


async def _ensure_session(runner: InMemoryRunner, user_id: str, session_id: str) -> None:
    existing = await runner.session_service.get_session(
        app_name=runner.app_name,
        user_id=user_id,
        session_id=session_id,
    )
    if existing is None:
        await runner.session_service.create_session(
            app_name=runner.app_name,
            user_id=user_id,
            session_id=session_id,
        )


def _build_runtime():
    config_text = """
agent:
  agent_id: "adk-multiagent-feature-matrix"
  agent_name: "ADK MultiAgent Feature Matrix"
  agent_type: "adk"
  version: "0.2.0"
  env: "dev"
  gcp_project: "local-project"

telemetry:
  enabled: true
  log_level: "INFO"
  cloud_logging:
    enabled: false
  tracing:
    enabled: true
    sample_rate: 1.0
    session_tracking:
      enabled: true
      session_attribute: "governance.session_id"
      user_attribute: "governance.user_id"
  cost_tracking:
    enabled: true
    pricing:
      "gpt-4o": { input: 2.50, output: 10.00 }
      "gpt-4o-mini": { input: 0.15, output: 0.60 }
    alert_threshold_usd: 0.000001
  metrics:
    enabled: true

guardrails:
  enabled: true
  profile: strict

dlp:
  enabled: true
  provider: model_armor
  scan_input: true
  scan_output: true
  scan_tool_params: true
  action_on_input_pii: log
  action_on_output_pii: log
  info_types:
    - EMAIL_ADDRESS
    - PHONE_NUMBER
    - US_SSN

registry:
  heartbeat_interval_s: 300
"""
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(config_text)
        path = f.name

    return init_governance(path, auto_register=True, start_heartbeat=False)


async def _run_query(
    *,
    runner: InMemoryRunner,
    governance,
    user_id: str,
    session_id: str,
    query: str,
    exporter,
) -> ScenarioResult:
    await _ensure_session(runner, user_id, session_id)

    before_spans = len(exporter.get_finished_spans())
    request_text, ctx, start = await governance.before_agent_call(
        governance.agent,
        query,
        user_id=user_id,
        session_id=session_id,
        prompt_text=INSTRUCTION,
    )

    content = types.Content(role="user", parts=[types.Part(text=request_text)])
    output = ""
    transfers: list[str] = []

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content,
    ):
        if not event.content or not event.content.parts:
            continue
        for part in event.content.parts:
            if part.function_call and part.function_call.name == "transfer_to_agent":
                target = str((part.function_call.args or {}).get("agent_name", ""))
                if target:
                    transfers.append(target)
            if part.text:
                output = part.text

    output = await governance.after_agent_call(governance.agent, ctx, output, start)

    # Enrich governance telemetry with delegation and cost using observed request artifacts.
    for hop_number, target in enumerate(transfers, start=1):
        chain = ["orchestrator", target]
        await governance.record_delegation(
            governance.agent,
            ctx,
            source_agent="orchestrator",
            target_agent=target,
            reason="feature_matrix_validation",
            hop_number=hop_number,
            chain=chain,
            method="sub_agent",
        )

    new_spans = exporter.get_finished_spans()[before_spans:]
    input_tokens = 0
    output_tokens = 0
    for span in new_spans:
        attrs = span.attributes or {}
        input_tokens += int(attrs.get("gen_ai.usage.input_tokens") or attrs.get("llm.token_usage.input") or 0)
        output_tokens += int(attrs.get("gen_ai.usage.output_tokens") or attrs.get("llm.token_usage.output") or 0)

    if input_tokens or output_tokens:
        settings = get_settings()
        await governance.record_llm_usage(
            governance.agent,
            ctx,
            model=settings.orchestrator_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            delegation_chain="orchestrator→" + "→".join(transfers) if transfers else "orchestrator",
        )

    return ScenarioResult(
        query=query,
        session_id=session_id,
        output=output,
        transfers=transfers,
        request_id=ctx.request_id,
    )


def _eval_run(agent_id: str, metric_value: float) -> EvalRunResult:
    now = datetime.now(timezone.utc)
    return EvalRunResult(
        agent_id=agent_id,
        started_at=now,
        finished_at=now,
        metrics=[
            EvalMetricResult(
                name="task_completion",
                value=metric_value,
                verdict=EvalVerdict.PASS,
                threshold=0.8,
            )
        ],
        overall=EvalVerdict.PASS,
    )


def _check(checks: list[FeatureCheck], name: str, condition: bool, details: str) -> None:
    checks.append(FeatureCheck(name=name, passed=bool(condition), details=details))


async def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    exporter = setup_telemetry(use_console=False)
    exporter.clear()

    runtime = _build_runtime()
    governance = runtime.middleware

    captured_events: list[dict[str, Any]] = []
    governance._logger._emit = lambda payload: captured_events.append(payload)  # type: ignore[attr-defined,assignment]

    runner = InMemoryRunner(agent=build_orchestrator(), app_name="feature_matrix")

    mode = "mock" if get_settings().mock_mode else "azure_openai"
    user_id = "feature-matrix-user"

    scenarios = [
        ("session-clean", "What is the capital of France?"),
        ("session-validate", "Validate this value: sample_data"),
        ("session-pii", "My email is alice@example.com and my SSN is 123-45-6789"),
        ("session-topic", "Tell me about banned_topic"),
    ]

    results: list[ScenarioResult] = []
    for session_id, query in scenarios:
        result = await _run_query(
            runner=runner,
            governance=governance,
            user_id=user_id,
            session_id=session_id,
            query=query,
            exporter=exporter,
        )
        results.append(result)

    spans = exporter.get_finished_spans()
    cloud_entries = spans_to_cloud_logging_entries(spans, project_id="local-project")

    checks: list[FeatureCheck] = []

    event_types = [e.get("event_type") for e in captured_events]
    _check(checks, "agent_request_start emitted", "agent_request_start" in event_types, str(event_types))
    _check(checks, "agent_request_end emitted", "agent_request_end" in event_types, str(event_types))
    _check(checks, "dlp_event emitted", "dlp_event" in event_types, str(event_types))
    _check(checks, "cost_event emitted", "cost_event" in event_types, str(event_types))
    _check(checks, "agent_delegation emitted", "agent_delegation" in event_types, str(event_types))
    _check(checks, "metric_event emitted", "metric_event" in event_types, str(event_types))

    start_events = [e for e in captured_events if e.get("event_type") == "agent_request_start"]
    has_prompt = any((ev.get("attributes") or {}).get("governance.prompt.fingerprint") for ev in start_events)
    _check(checks, "prompt fingerprint attributes present", has_prompt, f"start_events={len(start_events)}")

    pii_events = [e for e in captured_events if e.get("event_type") == "dlp_event"]
    has_pii_types = any((ev.get("attributes") or {}).get("info_types") for ev in pii_events)
    _check(checks, "dlp info types populated", has_pii_types, f"dlp_events={len(pii_events)}")

    # Span checks
    has_session_attr = any((s.attributes or {}).get("governance.session_id") for s in spans)
    _check(checks, "session span attributes present", has_session_attr, f"span_count={len(spans)}")

    has_delegation_span = any(s.name == "agent_delegation" for s in spans)
    _check(checks, "delegation span present", has_delegation_span, "search span name agent_delegation")

    has_cost_span = any(s.name == "llm_cost" for s in spans)
    _check(checks, "cost span present", has_cost_span, "search span name llm_cost")

    has_cloud_trace_fields = all(
        e.get("logging.googleapis.com/trace") and e.get("logging.googleapis.com/spanId") for e in cloud_entries
    )
    _check(checks, "cloud logging trace/span fields present", has_cloud_trace_fields, f"entries={len(cloud_entries)}")

    # Runtime metrics snapshot checks.
    snapshot = governance._metrics.snapshot()  # type: ignore[attr-defined]
    _check(checks, "runtime metrics snapshot generated", bool(snapshot), json.dumps(snapshot, default=str)[:2000])
    _check(checks, "delegation edges tracked", bool(snapshot.get("delegation_edges")), str(snapshot.get("delegation_edges")))

    # DLP provider mode checks.
    scanner_ma = DLPScanner.from_config({"provider": "model_armor", "action_on_input_pii": "log"})
    scanner_sdp = DLPScanner.from_config({"provider": "sensitive_data_protection", "action_on_input_pii": "log"})
    _check(checks, "dlp model_armor provider selectable", scanner_ma.provider == "model_armor", scanner_ma.provider)
    _check(
        checks,
        "dlp provider differentiation",
        len(scanner_sdp.info_types) >= len(scanner_ma.info_types),
        f"sdp={len(scanner_sdp.info_types)} model_armor={len(scanner_ma.info_types)}",
    )

    # Annotation and golden-data loop checks.
    annotation_store = JsonlAnnotationStore(ARTIFACTS_DIR / "annotations.feature_matrix.jsonl")
    annotation_client = AnnotationClient(annotation_store)
    await annotation_client.annotate(
        Annotation(
            trace_id="feature-trace-1",
            label="incorrect",
            note="feature-matrix annotation",
            annotator="automation:feature-matrix",
        )
    )
    exported = await annotation_client.export_annotated_traces("incorrect")
    _check(checks, "annotation export works", len(exported.items) >= 1, f"items={len(exported.items)}")

    capture = TraceCapture(events=captured_events)
    session_dataset = await capture.capture_from_session("session-clean")
    _check(
        checks,
        "trace capture by session works",
        len(session_dataset.items) >= 1,
        f"items={len(session_dataset.items)}",
    )

    # Experiment comparison checks.
    baseline = Experiment(name="baseline", dataset_name="feature-matrix", results=[_eval_run("agent", 0.8)])
    candidate = Experiment(name="candidate", dataset_name="feature-matrix", results=[_eval_run("agent", 0.9)])
    comparison = ExperimentComparison(baseline, candidate).compare()
    _check(
        checks,
        "experiment comparison computes deltas",
        comparison.deltas.get("task_completion") == 0.1,
        json.dumps(comparison.deltas),
    )

    passed = sum(1 for c in checks if c.passed)
    total = len(checks)

    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "execution_mode": mode,
        "azure_mock": get_settings().mock_mode,
        "results": [asdict(r) for r in results],
        "feature_checks": [asdict(c) for c in checks],
        "summary": {
            "passed": passed,
            "failed": total - passed,
            "total": total,
        },
    }

    JSON_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Governance Feature Matrix Report",
        "",
        f"- Mode: **{mode}**",
        f"- Passed: **{passed}/{total}**",
        "",
        "## Checks",
        "",
        "| Feature | Status | Details |",
        "|---|---|---|",
    ]
    for c in checks:
        status = "PASS" if c.passed else "FAIL"
        details = c.details.replace("\n", " ")[:200]
        lines.append(f"| {c.name} | {status} | {details} |")

    lines.extend([
        "",
        "## Scenario Outputs",
        "",
        "| Session | Query | Transfers | Output (trimmed) |",
        "|---|---|---|---|",
    ])
    for r in results:
        lines.append(
            f"| {r.session_id} | {r.query[:80]} | {','.join(r.transfers) if r.transfers else 'none'} | {r.output[:120]} |"
        )

    MD_REPORT.write_text("\n".join(lines), encoding="utf-8")

    runtime.lifecycle.mark_stopped()

    print(json.dumps(report["summary"], indent=2))
    print(f"JSON report: {JSON_REPORT}")
    print(f"Markdown report: {MD_REPORT}")

    if passed != total:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
