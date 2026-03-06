from datetime import datetime, timedelta, timezone

import pytest

from agent_governance.dlp import DLPScanner
from agent_governance.eval import Experiment, ExperimentComparison
from agent_governance.models import EvalMetricResult, EvalRunResult, EvalVerdict
from agent_governance.telemetry.annotations import Annotation, AnnotationClient, JsonlAnnotationStore
from agent_governance.golden_data.capture import TraceCapture


def _eval_run(agent_id: str, value: float) -> EvalRunResult:
    now = datetime.now(timezone.utc)
    return EvalRunResult(
        agent_id=agent_id,
        started_at=now,
        finished_at=now,
        metrics=[EvalMetricResult(name="task_completion", value=value, verdict=EvalVerdict.PASS, threshold=0.8)],
        overall=EvalVerdict.PASS,
    )


def test_dlp_model_armor_provider_scan():
    scanner = DLPScanner.from_config({"provider": "model_armor", "action_on_input_pii": "log"})
    _, scan = scanner.scan_and_process("Reach me at me@example.com", scanner.action)
    assert scanner.provider == "model_armor"
    assert scan.findings


def test_experiment_comparison_delta():
    baseline = Experiment(name="baseline", dataset_name="golden-v1", results=[_eval_run("a1", 0.8)])
    candidate = Experiment(name="candidate", dataset_name="golden-v1", results=[_eval_run("a1", 0.9)])

    report = ExperimentComparison(baseline, candidate).compare()

    assert report.deltas["task_completion"] == 0.1
    assert "task_completion" in report.improved_metrics


@pytest.mark.asyncio
async def test_annotations_export(tmp_path):
    store = JsonlAnnotationStore(tmp_path / "annotations.jsonl")
    client = AnnotationClient(store)

    await client.annotate(
        Annotation(
            trace_id="trace-1",
            label="incorrect",
            score=0.0,
            note="hallucination",
            annotator="human:test@example.com",
        )
    )

    dataset = await client.export_annotated_traces(
        "incorrect",
        date_range=(datetime.now(timezone.utc) - timedelta(days=1), datetime.now(timezone.utc) + timedelta(days=1)),
    )
    assert len(dataset.items) == 1
    assert dataset.items[0]["trace_id"] == "trace-1"


@pytest.mark.asyncio
async def test_trace_capture_from_session():
    events = [
        {
            "event_type": "agent_request_end",
            "agent": {"agent_id": "orchestrator"},
            "context": {"session_id": "s-1", "trace_id": "t-1", "request_id": "r-1"},
            "attributes": {"status": "success", "latency_ms": 120},
        }
    ]
    capture = TraceCapture(events=events)
    dataset = await capture.capture_from_session("s-1")
    assert len(dataset.items) == 1
    assert dataset.items[0]["session_id"] == "s-1"
