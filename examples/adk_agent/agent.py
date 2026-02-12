from agent_governance import GuardrailsEngine, DLPScanner, init_telemetry, load_config
from agent_governance.models import DLPAction, EventType, RequestContext
from agent_governance.telemetry.events import build_event


def main():
    cfg = load_config("governance.yaml")
    logger = init_telemetry(cfg.section("telemetry"))
    guardrails = GuardrailsEngine(cfg.section("guardrails"))
    dlp = DLPScanner(action=DLPAction.REDACT)

    # Example tool call validation
    result = guardrails.validate_tool_call("search", {"query": "hello"}, rate_key="user-1")
    logger.emit_event(
        build_event(
            EventType.GUARDRAIL_EVENT,
            cfg.agent,
            RequestContext(),
            {"result": result.model_dump()},
        )
    )

    scan = dlp.scan_text("email me at test@example.com")
    print(scan.model_dump())


if __name__ == "__main__":
    main()
