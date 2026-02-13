from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google.adk.runners import InMemoryRunner
from google.genai import types

from src.agents.orchestrator import build_orchestrator
from src.telemetry.setup import setup_telemetry
from src.telemetry.span_formatter import summarize_spans, spans_to_cloud_logging_entries


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


async def run_query(runner: InMemoryRunner, user_id: str, session_id: str, text: str) -> tuple[str, list[str]]:
    await _ensure_session(runner, user_id, session_id)
    content = types.Content(role="user", parts=[types.Part(text=text)])

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

    return last_text, transfer_targets


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
        answer, transfers = await run_query(runner, user_id, session_id, q)
        print("Q:", q)
        print("A:", answer)
        print("A2A transfers:", transfers if transfers else "none")
        print("-" * 60)

    spans = exporter.get_finished_spans()
    print_summary(spans)
    write_cloud_logging_jsonl(spans)


if __name__ == "__main__":
    asyncio.run(main())
