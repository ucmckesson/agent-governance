import pytest

from agent_governance.integrations import GovernanceADKMiddleware


@pytest.mark.asyncio
async def test_adk_middleware_flow(tmp_path):
    guardrails_path = tmp_path / "guardrails.yaml"
    guardrails_path.write_text(
        """
enabled: true
tools:
  default_policy:
    allowed: true
"""
    )

    schema_path = tmp_path / "model_schema.yaml"
    schema_path.write_text(
        """
input_schema:
  type: object
  properties:
    text:
      type: string
  required: ["text"]
output_schema:
  type: object
  properties:
    text:
      type: string
  required: ["text"]
"""
    )

    config_path = tmp_path / "governance.yaml"
    config_path.write_text(
        f"""
agent:
  agent_id: "test-agent"
  agent_name: "Test Agent"
  agent_type: "adk"
  version: "0.1.0"
  env: "dev"
  gcp_project: "test-project"

guardrails:
  policy_file: "{guardrails_path}"
  model_schema_file: "{schema_path}"

dlp:
  enabled: false
"""
    )

    governance = GovernanceADKMiddleware.from_config(str(config_path))
    agent = governance.agent

    processed_input, ctx, start_time = await governance.before_agent_call(agent, "hello", user_id="u1")
    assert processed_input == "hello"

    output = await governance.after_agent_call(agent, ctx, "response", start_time)
    assert output == "response"
