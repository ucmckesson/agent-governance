from __future__ import annotations

from google.adk.agents import LlmAgent

from ..config import get_settings
from ..guardrails.pii_guardrail import pii_input_guardrail
from ..guardrails.topic_guardrail import topic_input_guardrail
from ..guardrails.toxicity_guardrail import toxicity_output_guardrail
from ..model_wrapper import AzureOpenAILlm
from ..telemetry.error_handlers import on_model_error_callback
from ..tools.web_lookup import WebLookupTool


def build_research_agent() -> LlmAgent:
    settings = get_settings()
    return LlmAgent(
        name="research_agent",
        description="Handles factual research queries using a web lookup tool.",
        model=AzureOpenAILlm(settings.research_model, settings=settings),
        instruction=(
            "You are a research agent. Use the web_lookup tool for factual queries."
        ),
        tools=[WebLookupTool()],
        before_agent_callback=[pii_input_guardrail, topic_input_guardrail],
        after_model_callback=[toxicity_output_guardrail],
        on_model_error_callback=on_model_error_callback,
    )
