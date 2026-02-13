from __future__ import annotations

import re
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.genai import types

from ..telemetry.span_helpers import guardrail_span

PII_PATTERNS = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone": re.compile(r"\b\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}


def _extract_user_text(callback_context: CallbackContext) -> str:
    content = callback_context.user_content
    if not content or not content.parts:
        return ""
    return "\n".join([part.text for part in content.parts if part.text]).lower()


def pii_input_guardrail(callback_context: CallbackContext) -> Optional[types.Content]:
    user_text = _extract_user_text(callback_context)
    with guardrail_span("pii_guardrail", "input") as span:
        for label, pattern in PII_PATTERNS.items():
            if pattern.search(user_text):
                reason = f"PII detected: {label}"
                span.set_attribute("guardrail.result", "blocked")
                span.set_attribute("guardrail.reason", reason)
                return types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            text=(
                                f"Request blocked: {label} detected. "
                                "Please remove personal information."
                            )
                        )
                    ],
                )
        span.set_attribute("guardrail.result", "pass")
        span.set_attribute("guardrail.reason", "")
    return None
