from __future__ import annotations

import os
import uuid
from typing import Iterable, Tuple

import pytest
from google.adk.runners import InMemoryRunner
from google.genai import types

from src.agents.orchestrator import build_orchestrator
from src.telemetry.setup import setup_telemetry


@pytest.fixture(autouse=True)
def _env_defaults() -> None:
    os.environ.setdefault("AZURE_OPENAI_MOCK", "true")
    os.environ.setdefault("BANNED_TOPICS", "banned_topic")
    os.environ.setdefault("TOXICITY_REGEX", r"\b(hate|stupid|idiot)\b")


@pytest.fixture
def otel_exporter():
    exporter = setup_telemetry(use_console=False)
    yield exporter
    exporter.clear()


@pytest.fixture
def runner():
    orchestrator = build_orchestrator()
    return InMemoryRunner(agent=orchestrator, app_name="test_app")


@pytest.fixture
def session_ids() -> Tuple[str, str]:
    return "test_user", f"session-{uuid.uuid4()}"


def run_agent_query(runner: InMemoryRunner, user_id: str, session_id: str, text: str):
    content = types.Content(role="user", parts=[types.Part(text=text)])
    events = []
    async def _run():
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
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content,
        ):
            events.append(event)
    import asyncio
    asyncio.run(_run())
    return events


def extract_last_text(events) -> str:
    for event in reversed(events):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    return part.text
    return ""
