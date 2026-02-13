from __future__ import annotations

import json
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse
from google.genai import types
from jsonschema import Draft7Validator

from ..telemetry.span_helpers import guardrail_span


VALIDATOR_SCHEMA = {
    "type": "object",
    "properties": {
        "valid": {"type": "boolean"},
        "reasons": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["valid", "reasons"],
    "additionalProperties": False,
}

_validator = Draft7Validator(VALIDATOR_SCHEMA)


def _extract_text(llm_response: LlmResponse) -> str:
    if not llm_response.content or not llm_response.content.parts:
        return ""
    return "\n".join([part.text for part in llm_response.content.parts if part.text])


def schema_output_guardrail(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> Optional[LlmResponse]:
    if callback_context.agent_name != "validator_agent":
        return None

    text = _extract_text(llm_response)
    if not text:
        return None

    with guardrail_span("schema_guardrail", "output") as span:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            span.set_attribute("guardrail.result", "blocked")
            span.set_attribute("guardrail.reason", "invalid JSON")
            content = types.Content(
                role="model",
                parts=[types.Part(text="Response blocked: invalid JSON schema.")],
            )
            return LlmResponse(content=content)

        errors = sorted(_validator.iter_errors(payload), key=lambda e: e.path)
        if errors:
            span.set_attribute("guardrail.result", "blocked")
            span.set_attribute("guardrail.reason", errors[0].message)
            content = types.Content(
                role="model",
                parts=[types.Part(text="Response blocked: schema validation failed.")],
            )
            return LlmResponse(content=content)

        span.set_attribute("guardrail.result", "pass")
        span.set_attribute("guardrail.reason", "")
    return None
