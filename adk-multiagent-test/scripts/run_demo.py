from __future__ import annotations

import asyncio
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google.adk.runners import InMemoryRunner
from google.genai import types

from src.agents.orchestrator import build_orchestrator
from src.telemetry.setup import setup_telemetry


async def run_query(runner: InMemoryRunner, user_id: str, session_id: str, text: str) -> str:
    content = types.Content(role="user", parts=[types.Part(text=text)])
    last_text = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    last_text = part.text
    return last_text


def main() -> None:
    exporter = setup_telemetry(use_console=True)
    runner = InMemoryRunner(agent=build_orchestrator(), app_name="demo_app")

    async def _run():
        user_id = "demo-user"
        session_id = "demo-session"
        queries = [
            "What is the capital of France?",
            "Validate this email: test@example.com",
            "Research the GDP of Japan and validate the data format",
        ]
        for q in queries:
            answer = await run_query(runner, user_id, session_id, q)
            print(f"Q: {q}")
            print(f"A: {answer}\n")

        spans = exporter.get_finished_spans()
        print(f"Captured spans: {len(spans)}")

    asyncio.run(_run())


if __name__ == "__main__":
    main()
