from __future__ import annotations

from tests.conftest import extract_last_text, run_agent_query


def test_input_pii_blocked(runner, session_ids, otel_exporter):
    user_id, session_id = session_ids
    events = run_agent_query(runner, user_id, session_id, "My SSN is 123-45-6789")
    text = extract_last_text(events)
    assert "blocked" in text.lower()

    spans = otel_exporter.get_finished_spans()
    guardrail_spans = [s for s in spans if s.attributes.get("guardrail.name") == "pii_guardrail"]
    assert guardrail_spans


def test_input_topic_blocked(runner, session_ids):
    user_id, session_id = session_ids
    events = run_agent_query(runner, user_id, session_id, "Tell me about banned_topic")
    text = extract_last_text(events)
    assert "banned" in text.lower()


def test_input_clean_passthrough(runner, session_ids, otel_exporter):
    user_id, session_id = session_ids
    _ = run_agent_query(runner, user_id, session_id, "What is quantum computing?")
    spans = otel_exporter.get_finished_spans()
    guardrail_spans = [s for s in spans if s.attributes.get("guardrail.type") == "input"]
    assert guardrail_spans
    assert all(s.attributes.get("guardrail.result") in {"pass", "blocked"} for s in guardrail_spans)


def test_output_schema_violation(runner, session_ids):
    user_id, session_id = session_ids
    events = run_agent_query(runner, user_id, session_id, "Validate malformed response")
    text = extract_last_text(events)
    assert "schema" in text.lower() or "invalid" in text.lower()


def test_output_toxicity_caught(runner, session_ids):
    user_id, session_id = session_ids
    events = run_agent_query(runner, user_id, session_id, "Validate toxic response")
    text = extract_last_text(events)
    assert "blocked" in text.lower()


def test_stacked_guardrails_order(runner, session_ids, otel_exporter):
    user_id, session_id = session_ids
    _ = run_agent_query(runner, user_id, session_id, "What is quantum computing?")
    spans = [s for s in otel_exporter.get_finished_spans() if s.attributes.get("guardrail.type") == "input"]
    names = [s.attributes.get("guardrail.name") for s in spans]
    assert "pii_guardrail" in names and "topic_blocklist" in names
