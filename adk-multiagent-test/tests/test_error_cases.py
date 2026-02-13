from __future__ import annotations

from tests.conftest import extract_last_text, run_agent_query


def test_azure_openai_timeout(runner, session_ids, otel_exporter):
    user_id, session_id = session_ids
    events = run_agent_query(runner, user_id, session_id, "timeout")
    text = extract_last_text(events)
    assert "error" in text.lower()

    spans = otel_exporter.get_finished_spans()
    assert any(s.attributes.get("error") for s in spans)


def test_unknown_query_type(runner, session_ids):
    user_id, session_id = session_ids
    events = run_agent_query(runner, user_id, session_id, "asdfghjkl random gibberish")
    text = extract_last_text(events)
    assert "route" in text.lower()


def test_agent_transfer_failure(runner, session_ids):
    user_id, session_id = session_ids
    events = run_agent_query(runner, user_id, session_id, "transfer_fail")
    text = extract_last_text(events)
    assert "error" in text.lower() or "route" in text.lower()
