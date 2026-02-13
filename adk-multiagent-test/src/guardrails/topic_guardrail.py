from __future__ import annotations

from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.genai import types

from ..config import get_settings, iter_banned_topics
from ..telemetry.span_helpers import guardrail_span


def _extract_user_text(callback_context: CallbackContext) -> str:
    content = callback_context.user_content
    if not content or not content.parts:
        return ""
    return "\n".join([part.text for part in content.parts if part.text]).lower()


def topic_input_guardrail(callback_context: CallbackContext) -> Optional[types.Content]:
    settings = get_settings()
    user_text = _extract_user_text(callback_context)
    with guardrail_span("topic_blocklist", "input") as span:
        for topic in iter_banned_topics(settings):
            if topic.lower() in user_text:
                reason = f"Blocked topic: {topic}"
                span.set_attribute("guardrail.result", "blocked")
                span.set_attribute("guardrail.reason", reason)
                return types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            text=f"Request blocked due to banned topic: {topic}."
                        )
                    ],
                )
        span.set_attribute("guardrail.result", "pass")
        span.set_attribute("guardrail.reason", "")
    return None
