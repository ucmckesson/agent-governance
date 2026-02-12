import pytest

from agent_governance.guardrails.engine import GuardrailsEngine
from agent_governance.models import GuardrailAction, RequestContext


@pytest.mark.asyncio
async def test_tool_blocked_by_default():
    config = {
        "enabled": True,
        "tools": {"default_policy": {"allowed": False}, "policies": []},
    }
    engine = GuardrailsEngine(config)
    result = await engine.check_tool_call(RequestContext(), "unknown_tool", {}, agent=None)
    assert result.action == GuardrailAction.BLOCK


@pytest.mark.asyncio
async def test_tool_requires_confirmation():
    config = {
        "enabled": True,
        "tools": {
            "default_policy": {"allowed": False},
            "policies": [
                {"tool_name": "delete_record", "allowed": True, "requires_confirmation": True}
            ],
        },
    }
    engine = GuardrailsEngine(config)
    result = await engine.check_tool_call(RequestContext(), "delete_record", {}, agent=None)
    assert result.action == GuardrailAction.CONFIRM


@pytest.mark.asyncio
async def test_input_schema_validation(tmp_path):
    schema = """
input_schema:
  type: object
  properties:
    text:
      type: string
      minLength: 5
  required: ["text"]
"""
    schema_path = tmp_path / "model_schema.yaml"
    schema_path.write_text(schema)

    config = {
        "enabled": True,
        "model_schema_file": str(schema_path),
    }
    engine = GuardrailsEngine(config)
    result = await engine.check_input(RequestContext(), "hi", agent=None)
    assert result.action == GuardrailAction.BLOCK
    assert result.rule_name == "input_schema"
