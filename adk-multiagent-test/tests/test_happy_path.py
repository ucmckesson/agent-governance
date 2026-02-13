from __future__ import annotations

from tests.conftest import extract_last_text, run_agent_query


def test_simple_research_query(runner, session_ids, otel_exporter):
    user_id, session_id = session_ids
    events = run_agent_query(runner, user_id, session_id, "What is the capital of France?")
    text = extract_last_text(events)
    assert "Paris" in text

    transfer_calls = []
    for event in events:
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.function_call and part.function_call.name == "transfer_to_agent":
                    transfer_calls.append(part.function_call)
    assert transfer_calls
    assert all(call.args.get("agent_name") for call in transfer_calls)

    spans = otel_exporter.get_finished_spans()
    tool_spans = [s for s in spans if s.attributes.get("gen_ai.tool.name") == "web_lookup"]
    assert tool_spans


def test_simple_validation_query(runner, session_ids, otel_exporter):
    user_id, session_id = session_ids
    events = run_agent_query(runner, user_id, session_id, "Validate this value: sample_data")
    text = extract_last_text(events)
    assert "valid" in text


def test_multi_hop_delegation(runner, session_ids, otel_exporter):
    user_id, session_id = session_ids
    events = run_agent_query(
        runner,
        user_id,
        session_id,
        "Research the GDP of Japan and validate the data format",
    )
    text = extract_last_text(events)
    assert "valid" in text

    spans = otel_exporter.get_finished_spans()
    tool_spans = [s for s in spans if s.attributes.get("gen_ai.tool.name") == "web_lookup"]
    assert tool_spans
