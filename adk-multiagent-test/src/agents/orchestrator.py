from __future__ import annotations

from google.adk.agents import LlmAgent

from ..config import get_settings
from ..guardrails.pii_guardrail import pii_input_guardrail
from ..guardrails.topic_guardrail import topic_input_guardrail
from ..guardrails.toxicity_guardrail import toxicity_output_guardrail
from ..model_wrapper import AzureOpenAILlm
from ..telemetry.error_handlers import on_model_error_callback
from .research_agent import build_research_agent
from .validator_agent import build_validator_agent


INSTRUCTION = (
    "You are an orchestration agent.\n"
    "Route research/factual questions to research_agent.\n"
    "Route validation requests to validator_agent.\n"
    "If both are required, delegate to research_agent first and then validator_agent.\n"
    "Use the transfer_to_agent tool when delegating."
)


def build_orchestrator() -> LlmAgent:
    settings = get_settings()
    research_agent = build_research_agent()
    validator_agent = build_validator_agent()

    return LlmAgent(
        name="orchestrator",
        description="Routes requests to specialist agents.",
        model=AzureOpenAILlm(settings.orchestrator_model, settings=settings),
        instruction=INSTRUCTION,
        sub_agents=[research_agent, validator_agent],
        before_agent_callback=[pii_input_guardrail, topic_input_guardrail],
        after_model_callback=[toxicity_output_guardrail],
        on_model_error_callback=on_model_error_callback,
    )
