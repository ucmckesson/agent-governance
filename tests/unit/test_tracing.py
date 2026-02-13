import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agent_governance.telemetry import init_tracing
from agent_governance.telemetry.spans import start_span
from agent_governance.models import RequestContext


def _has_otel_sdk() -> bool:
    try:
        from opentelemetry.sdk.trace.export import InMemorySpanExporter  # noqa: F401

        return True
    except Exception:
        return False


@pytest.mark.skipif(not _has_otel_sdk(), reason="opentelemetry-sdk not installed")
def test_tracing_creates_spans(monkeypatch):
    from opentelemetry.sdk.trace.export import InMemorySpanExporter, SimpleSpanProcessor
    from opentelemetry import trace

    exporter = InMemorySpanExporter()

    def _create_exporter():
        return exporter

    monkeypatch.setattr("agent_governance.telemetry.tracing._create_exporter", _create_exporter)
    monkeypatch.setattr("agent_governance.telemetry.tracing._otel_sdk_available", lambda: True)

    class Agent:
        agent_id = "demo-agent"
        version = "0.1.1"
        env = "dev"
        region = "us-central1"
        gcp_project = "demo-project"
        agent_type = "custom"

    init_tracing(Agent(), {"tracing": {"enabled": True, "sample_rate": 1.0}})

    provider = trace.get_tracer_provider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    with start_span("agent_request"):
        ctx = RequestContext()
        assert ctx.trace_id is not None
        assert ctx.span_id is not None

    provider.force_flush()
    spans = exporter.get_finished_spans()
    assert any(span.name == "agent_request" for span in spans)
