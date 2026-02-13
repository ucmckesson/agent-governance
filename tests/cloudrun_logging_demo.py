"""Emit telemetry events to Cloud Logging (or stdout) for validation."""

from agent_governance import AgentIdentity, RequestContext, init_telemetry
from agent_governance.models import AgentType, Environment, EventType
from agent_governance.telemetry.events import build_event


def main() -> None:
    logger = init_telemetry(
        {
            "log_level": "INFO",
            "cloud_logging": {
                "enabled": True,
                "log_name": "agent-governance-demo",
                "labels": {"service": "demo-agent"},
                "also_stdout": True,
            },
        }
    )

    agent = AgentIdentity(
        agent_id="demo-agent",
        agent_name="Demo Agent",
        agent_type=AgentType.CUSTOM,
        version="0.1.1",
        env=Environment.DEV,
        gcp_project="demo-project",
        region="us-central1",
    )
    ctx = RequestContext(user_id_hash=RequestContext.hash_user_id("user-1"))

    logger.emit_event(build_event(EventType.AGENT_REQUEST_START, agent, ctx))
    logger.emit_event(build_event(EventType.AGENT_REQUEST_END, agent, ctx, {"status": "success"}))


if __name__ == "__main__":
    main()
