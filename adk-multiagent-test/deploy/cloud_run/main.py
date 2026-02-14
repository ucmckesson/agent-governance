from __future__ import annotations

import os
from pathlib import Path
import sys
from uuid import uuid4

from fastapi import FastAPI
from pydantic import BaseModel

from google.adk.runners import InMemoryRunner
from google.genai import types

from agent_governance.integrations import cloud_run_fastapi_runtime
from agent_governance.exceptions import InputBlockedError, OutputBlockedError

HARNESS_ROOT = Path(__file__).resolve().parents[2]
if str(HARNESS_ROOT) not in sys.path:
    sys.path.insert(0, str(HARNESS_ROOT))

from src.agents.orchestrator import build_orchestrator


class InvokeRequest(BaseModel):
    text: str
    user_id: str = "cloudrun-user"
    session_id: str | None = None


DEFAULT_CONFIG = str(Path(__file__).with_name("governance.yaml"))
CONFIG_PATH = os.environ.get("GOVERNANCE_CONFIG_PATH", DEFAULT_CONFIG)

app = FastAPI(title="adk-multiagent-cloudrun")
runtime = cloud_run_fastapi_runtime(app, config_path=CONFIG_PATH)
governance = runtime.middleware
runner = InMemoryRunner(agent=build_orchestrator(), app_name="adk_cloudrun")


async def _ensure_session(user_id: str, session_id: str) -> None:
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


async def _run_query(text: str, user_id: str, session_id: str) -> tuple[str, list[str]]:
    await _ensure_session(user_id, session_id)

    request_text, gov_ctx, gov_start = await governance.before_agent_call(
        governance.agent,
        text,
        user_id=user_id,
        session_id=session_id,
    )

    content = types.Content(role="user", parts=[types.Part(text=request_text)])
    response_text = ""
    transfers: list[str] = []

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content,
    ):
        if not event.content or not event.content.parts:
            continue

        for part in event.content.parts:
            if part.function_call and part.function_call.name == "transfer_to_agent":
                target = str((part.function_call.args or {}).get("agent_name", ""))
                if target:
                    transfers.append(target)
            if part.text:
                response_text = part.text

    final_text = await governance.after_agent_call(
        governance.agent,
        gov_ctx,
        response_text,
        gov_start,
    )
    return final_text, transfers


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "agent_id": runtime.config.agent.agent_id,
        "runtime": runtime.runtime.platform,
    }


@app.post("/invoke")
async def invoke(req: InvokeRequest) -> dict:
    session_id = req.session_id or f"session-{uuid4().hex[:10]}"
    try:
        output, transfers = await _run_query(req.text, req.user_id, session_id)
        return {
            "ok": True,
            "user_id": req.user_id,
            "session_id": session_id,
            "output": output,
            "transfers": transfers,
        }
    except InputBlockedError as exc:
        return {"ok": False, "blocked": "input", "reason": str(exc)}
    except OutputBlockedError as exc:
        return {"ok": False, "blocked": "output", "reason": str(exc)}


@app.post("/smoke")
async def smoke() -> dict:
    output, transfers = await _run_query(
        "What is the capital of France?",
        user_id="smoke-user",
        session_id=f"smoke-{uuid4().hex[:8]}",
    )
    return {"ok": True, "output": output, "transfers": transfers}
