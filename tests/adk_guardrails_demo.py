"""Ad-hoc guardrails demo using agent_governance + google-adk.

This script intentionally triggers a guardrails block.
"""

import asyncio
from pathlib import Path
import tempfile

from agent_governance.integrations import GovernanceADKMiddleware
from agent_governance.exceptions import ToolBlockedError

try:
    from google.adk import Agent  # noqa: F401
except Exception:
    Agent = None


def _write_config(tmp: Path) -> Path:
    guardrails = tmp / "guardrails.yaml"
    guardrails.write_text(
        """
enabled: true
tools:
  default_policy:
    allowed: false
  policies:
    - tool_name: "search"
      allowed: false
"""
    )

    cfg = tmp / "governance.yaml"
    cfg.write_text(
        f"""
agent:
  agent_id: "demo-agent"
  agent_name: "Demo Agent"
  agent_type: "adk"
  version: "0.1.1"
  env: "dev"
  gcp_project: "demo-project"

guardrails:
  policy_file: "{guardrails}"

dlp:
  enabled: false
"""
    )
    return cfg


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = _write_config(Path(tmpdir))
        governance = GovernanceADKMiddleware.from_config(str(cfg_path))
        agent = governance.agent

        processed_input, ctx, start_time = await governance.before_agent_call(
            agent, "hello", user_id="user-1"
        )
        _ = processed_input

        try:
            await governance.before_tool_call(agent, ctx, "search", {"query": "test"})
        except ToolBlockedError as exc:
            print(f"Guardrails blocked tool call as expected: {exc}")
            return

        print("Expected ToolBlockedError but none was raised")

        # Complete the request to keep telemetry flow consistent.
        await governance.after_agent_call(agent, ctx, "ok", start_time)


if __name__ == "__main__":
    asyncio.run(main())
