from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SDK_SRC = PROJECT_ROOT.parent / "src"
if str(SDK_SRC) not in sys.path:
    sys.path.insert(0, str(SDK_SRC))

from google.adk.runners import InMemoryRunner
from google.genai import types

from src.agents.orchestrator import build_orchestrator
from src.telemetry.setup import setup_telemetry
from src.telemetry.span_formatter import summarize_spans, spans_to_cloud_logging_entries

from agent_governance.integrations import GovernanceADKMiddleware
from agent_governance.exceptions import InputBlockedError, OutputBlockedError


ARTIFACT_DIR = Path("artifacts")
SPANS_JSONL = ARTIFACT_DIR / "spans.cloudlogging.jsonl"


async def _ensure_session(runner: InMemoryRunner, user_id: str, session_id: str) -> None:
    existing = await runner.session_service.get_session(
        app_name=runner.app_name,
        user_id=user_id,
        session_id=session_id,
    )
    if existing is None:
        await runner.session_service.create_session(
            app_name=runner.app_name,
            user_id=user_id,
            session_id=session_id,
        )


async def run_query(
    runner: InMemoryRunner,
    user_id: str,
    session_id: str,
    text: str,
    governance: GovernanceADKMiddleware | None = None,
) -> tuple[str, list[str]]:
    await _ensure_session(runner, user_id, session_id)
    request_text = text
    gov_ctx = None
    gov_start = None
    if governance is not None:
        try:
            request_text, gov_ctx, gov_start = await governance.before_agent_call(
                governance.agent,
                request_text,
                user_id=user_id,
                session_id=session_id,
            )
        except InputBlockedError as exc:
            return f"Blocked by governance: {exc}", []

    content = types.Content(role="user", parts=[types.Part(text=request_text)])

    last_text = ""
    transfer_targets: list[str] = []

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.function_call and part.function_call.name == "transfer_to_agent":
                    target = str((part.function_call.args or {}).get("agent_name", ""))
                    if target:
                        transfer_targets.append(target)
                if part.text:
                    last_text = part.text

    if governance is not None and gov_ctx is not None and gov_start is not None:
        try:
            last_text = await governance.after_agent_call(
                governance.agent,
                gov_ctx,
                last_text,
                gov_start,
            )
        except OutputBlockedError as exc:
            last_text = f"Blocked by governance: {exc}"

    return last_text, transfer_targets


def _build_governance_middleware() -> GovernanceADKMiddleware:
        config_text = """
agent:
    agent_id: "adk-multiagent-e2e"
    agent_name: "ADK MultiAgent E2E"
    agent_type: "adk"
    version: "0.1.1"
    env: "dev"
    gcp_project: "local-project"

telemetry:
    log_level: "INFO"
    cloud_logging:
        enabled: false

guardrails:
    enabled: true
    input_validation:
        block_known_injection_patterns: true
    content_safety:
        enabled: true
        topic_blocklist: []

dlp:
    enabled: true
    scan_input: true
    scan_output: true
    action_on_input_pii: "log"
    action_on_output_pii: "log"
    info_types:
        - "EMAIL_ADDRESS"
        - "PHONE_NUMBER"
        - "SSN"
"""
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
                f.write(config_text)
                path = f.name
        return GovernanceADKMiddleware.from_config(path)


def print_summary(spans) -> None:
    summary = summarize_spans(spans)
    print("\n=== OTel Summary ===")
    print(json.dumps(summary, indent=2))


def write_cloud_logging_jsonl(spans) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    project_id = os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    entries = spans_to_cloud_logging_entries(spans, project_id=project_id)
    with SPANS_JSONL.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"\nWrote cloud-logging-ready span records: {SPANS_JSONL}")


async def main() -> None:
    exporter = setup_telemetry(use_console=False)
    governance = _build_governance_middleware()

    runner = InMemoryRunner(agent=build_orchestrator(), app_name="azure_adk_e2e")
    user_id = "azure-user"
    session_id = "azure-session"

    queries = [
        "What is the capital of France?",
        "Validate this value: sample_data",
        "Research the GDP of Japan and validate the data format",
    ]

    print("AZURE_OPENAI_MOCK:", os.environ.get("AZURE_OPENAI_MOCK", "true"))
    print("Running ADK multi-agent scenarios...\n")

    for q in queries:
        answer, transfers = await run_query(runner, user_id, session_id, q, governance=governance)
        print("Q:", q)
        print("A:", answer)
        print("A2A transfers:", transfers if transfers else "none")
        print("-" * 60)

    spans = exporter.get_finished_spans()
    print_summary(spans)
    write_cloud_logging_jsonl(spans)


if __name__ == "__main__":
    asyncio.run(main())
