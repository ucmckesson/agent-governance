"""End-to-end demo: ADK integration + telemetry + guardrails + OTel spans.

This script runs a mock agent flow, emits structured logs, and creates spans
(if OTel SDK is installed). It also logs the guardrails policy metadata.
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import tempfile

from agent_governance.integrations import GovernanceADKMiddleware
from agent_governance.exceptions import ToolBlockedError, InputBlockedError
from agent_governance.models import EventType, RequestContext
from agent_governance.telemetry.events import build_event


def _write_config(tmp: Path) -> Path:
    cfg = tmp / "governance.yaml"
    cfg.write_text(
        """
agent:
  agent_id: "e2e-agent"
  agent_name: "E2E Agent"
  agent_type: "adk"
  version: "0.1.1"
  env: "dev"
  gcp_project: "demo-project"

telemetry:
  enabled: true
  log_level: "INFO"
  tracing:
    enabled: true
    sample_rate: 1.0
    dev_console: true

dlp:
  enabled: true
  scan_input: true
  action_on_input_pii: "redact"
  info_types:
    - "EMAIL_ADDRESS"
    - "PHONE_NUMBER"
    - "SSN"
    - "CREDIT_CARD"
"""
    )
    return cfg


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = _write_config(Path(tmpdir))
        governance = GovernanceADKMiddleware.from_config(str(cfg_path))
        agent = governance.agent

        # Emit a log with guardrails metadata (default policy)
        ctx = RequestContext(user_id_hash=RequestContext.hash_user_id("user-1"))
        governance._logger.emit_event(
            build_event(
                EventType.GUARDRAIL_EVENT,
                agent,
                ctx,
                {
                    "guardrails_policy": "default_strict",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        )

        user_input = "Email me at user@example.com and call +1-415-555-1234"
        try:
            processed_input, ctx, start_time = await governance.before_agent_call(
                agent, user_input, user_id="user-1"
            )
        except InputBlockedError as exc:
            print(f"Input blocked: {exc}")
            return

        print("Original:", user_input)
        print("Sanitized:", processed_input)

        # Guardrails tool call (should block by default strict policy)
        try:
            await governance.before_tool_call(agent, ctx, "execute_shell", {"cmd": "ls"})
        except ToolBlockedError as exc:
            print(f"Tool blocked as expected: {exc}")

        # Simulate response
        output = "Ok."
        await governance.after_agent_call(agent, ctx, output, start_time)


if __name__ == "__main__":
    asyncio.run(main())
