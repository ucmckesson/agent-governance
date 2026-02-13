from __future__ import annotations

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.genai import types
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode


def on_model_error_callback(
    callback_context: CallbackContext, llm_request: LlmRequest, error: Exception
) -> LlmResponse:
    span = trace.get_current_span()
    if span:
        span.record_exception(error)
        span.set_status(Status(StatusCode.ERROR, str(error)))
        span.set_attribute("error", True)
        span.set_attribute("error.message", str(error))

    content = types.Content(
        role="model",
        parts=[types.Part(text=f"Model error: {error}")],
    )
    return LlmResponse(content=content, error_message=str(error))
