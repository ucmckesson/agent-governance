from __future__ import annotations

from google.adk.agents import LlmAgent

from ..config import get_settings
from ..guardrails.pii_guardrail import pii_input_guardrail
from ..guardrails.schema_guardrail import schema_output_guardrail
from ..guardrails.topic_guardrail import topic_input_guardrail
from ..guardrails.toxicity_guardrail import toxicity_output_guardrail
from ..model_wrapper import AzureOpenAILlm
from ..telemetry.error_handlers import on_model_error_callback
from ..tools.validate_data import ValidateDataTool


def build_validator_agent() -> LlmAgent:
    settings = get_settings()
    return LlmAgent(
        name="validator_agent",
        description="Validates structured data and returns JSON results.",
        model=AzureOpenAILlm(settings.validator_model, settings=settings),
        instruction=(
            "You validate data inputs. Use validate_data tool."
            " Return JSON with keys: valid (bool) and reasons (list of strings)."
        ),
        tools=[ValidateDataTool()],
        before_agent_callback=[pii_input_guardrail, topic_input_guardrail],
        after_model_callback=[toxicity_output_guardrail, schema_output_guardrail],
        on_model_error_callback=on_model_error_callback,
    )
