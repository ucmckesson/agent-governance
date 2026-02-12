from agent_governance.models import AgentIdentity, AgentType, Environment, EventType, RequestContext
from agent_governance.telemetry.logger import GovernanceLogger
from agent_governance.telemetry.events import build_event


def test_telemetry_redaction_and_custom_fields():
    logger = GovernanceLogger(redaction_keys=["secret"], custom_fields={"team": "cx"})
    payloads = []

    def _capture(payload):
        payloads.append(payload)

    logger._emit = _capture  # type: ignore[assignment]

    agent = AgentIdentity(
        agent_id="a1",
        agent_name="Agent",
        agent_type=AgentType.CUSTOM,
        version="0.1.0",
        env=Environment.DEV,
        gcp_project="p1",
    )
    ctx = RequestContext()
    logger.emit_event(build_event(EventType.ERROR_EVENT, agent, ctx, {"secret": "value"}))

    assert payloads
    assert payloads[0]["attributes"]["secret"] == "[REDACTED]"
    assert payloads[0]["attributes"]["team"] == "cx"
