from __future__ import annotations

from tests.conftest import run_agent_query


def test_trace_id_consistency(runner, session_ids, otel_exporter):
    user_id, session_id = session_ids
    _ = run_agent_query(runner, user_id, session_id, "What is quantum computing?")

    spans = otel_exporter.get_finished_spans()
    trace_ids = {s.context.trace_id for s in spans}
    assert len(trace_ids) == 1


def test_span_parent_child_hierarchy(runner, session_ids, otel_exporter):
    user_id, session_id = session_ids
    _ = run_agent_query(runner, user_id, session_id, "What is the capital of France?")

    spans = otel_exporter.get_finished_spans()
    root_spans = [s for s in spans if s.parent is None]
    assert root_spans

    agent_spans = [s for s in spans if s.attributes.get("gen_ai.agent.name")]
    assert any(s.attributes.get("gen_ai.agent.name") == "orchestrator" for s in agent_spans)


def test_llm_spans_have_token_counts(runner, session_ids, otel_exporter):
    user_id, session_id = session_ids
    _ = run_agent_query(runner, user_id, session_id, "What is quantum computing?")

    spans = otel_exporter.get_finished_spans()
    llm_spans = [s for s in spans if s.name == "call_llm"]
    assert llm_spans
    assert all(
        s.attributes.get("gen_ai.usage.input_tokens")
        and s.attributes.get("gen_ai.usage.output_tokens")
        for s in llm_spans
    )


def test_tool_spans_have_io(runner, session_ids, otel_exporter):
    user_id, session_id = session_ids
    _ = run_agent_query(runner, user_id, session_id, "What is the capital of France?")

    spans = otel_exporter.get_finished_spans()
    tool_spans = [s for s in spans if s.attributes.get("gen_ai.tool.name")]
    assert tool_spans
    assert all(s.attributes.get("gcp.vertex.agent.tool_call_args") for s in tool_spans)
    assert all(s.attributes.get("gcp.vertex.agent.tool_response") for s in tool_spans)


def test_guardrail_spans_have_metadata(runner, session_ids, otel_exporter):
    user_id, session_id = session_ids
    _ = run_agent_query(runner, user_id, session_id, "What is quantum computing?")

    spans = otel_exporter.get_finished_spans()
    guardrail_spans = [s for s in spans if s.attributes.get("guardrail.name")]
    assert guardrail_spans
    assert all(s.attributes.get("guardrail.type") for s in guardrail_spans)
    assert all(s.attributes.get("guardrail.result") for s in guardrail_spans)


def test_a2a_spans_present(runner, session_ids, otel_exporter):
    user_id, session_id = session_ids
    _ = run_agent_query(runner, user_id, session_id, "What is the capital of France?")

    spans = otel_exporter.get_finished_spans()
    a2a_spans = [s for s in spans if s.attributes.get("a2a.target_agent")]
    assert a2a_spans


def test_latency_recorded(runner, session_ids, otel_exporter):
    user_id, session_id = session_ids
    _ = run_agent_query(runner, user_id, session_id, "What is quantum computing?")

    spans = otel_exporter.get_finished_spans()
    latency_spans = [s for s in spans if s.attributes.get("llm.latency_ms") is not None]
    assert latency_spans
    assert all(s.attributes.get("llm.latency_ms") >= 1 for s in latency_spans)
