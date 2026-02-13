from __future__ import annotations

import re
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse
from google.genai import types

from ..config import get_settings
from ..telemetry.span_helpers import guardrail_span


def _extract_text_from_response(llm_response: LlmResponse) -> str:
    if not llm_response.content or not llm_response.content.parts:
        return ""
    return "\n".join([part.text for part in llm_response.content.parts if part.text])


def toxicity_output_guardrail(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> Optional[LlmResponse]:
    settings = get_settings()
    text = _extract_text_from_response(llm_response)
    if not text:
        return None

    pattern = re.compile(settings.toxicity_regex, re.IGNORECASE)
    with guardrail_span("toxicity_guardrail", "output") as span:
        if pattern.search(text):
            span.set_attribute("guardrail.result", "blocked")
            span.set_attribute("guardrail.reason", "toxicity detected")
            content = types.Content(
                role="model",
                parts=[types.Part(text="Response blocked due to toxicity.")],
            )
            return LlmResponse(content=content)
        span.set_attribute("guardrail.result", "pass")
        span.set_attribute("guardrail.reason", "")
    return None
