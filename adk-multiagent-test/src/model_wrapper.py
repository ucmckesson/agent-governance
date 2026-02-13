from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncGenerator

import requests
from google.adk.models import BaseLlm, LlmRequest, LlmResponse
from google.genai import types
from opentelemetry import trace

from .config import Settings, ensure_settings_valid, get_settings


_AAD_TOKEN_CACHE: dict[str, float] | None = None

_TYPE_MAP = {
    "STRING": "string",
    "OBJECT": "object",
    "ARRAY": "array",
    "NUMBER": "number",
    "INTEGER": "integer",
    "BOOLEAN": "boolean",
    "NULL": "null",
}


def _get_access_token(settings: Settings) -> str:
    global _AAD_TOKEN_CACHE
    if not settings.azure_openai_token_url:
        raise ValueError("AZURE_OPENAI_TOKEN_URL is required for client credentials auth")

    now = time.time()
    if _AAD_TOKEN_CACHE and _AAD_TOKEN_CACHE["expires_at"] - 60 > now:
        return _AAD_TOKEN_CACHE["token"]

    if not settings.azure_openai_client_id or not settings.azure_openai_client_secret:
        raise ValueError("AZURE_OPENAI_CLIENT_ID and AZURE_OPENAI_CLIENT_SECRET are required")

    data = {
        "grant_type": "client_credentials",
        "client_id": settings.azure_openai_client_id,
        "client_secret": settings.azure_openai_client_secret,
        "scope": settings.azure_openai_scope,
    }
    resp = requests.post(
        settings.azure_openai_token_url,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=data,
        timeout=30,
        verify=False if settings.azure_openai_skip_verify else (settings.azure_openai_ca_bundle or True),
    )
    resp.raise_for_status()
    payload = resp.json()
    token = payload["access_token"]
    expires_in = int(payload.get("expires_in", 3600))
    _AAD_TOKEN_CACHE = {"token": token, "expires_at": now + expires_in}
    return token


class AzureOpenAILlm(BaseLlm):
    model: str

    def __init__(self, model: str, settings: Settings | None = None):
        super().__init__(model=model)
        self._settings = settings or get_settings()
        ensure_settings_valid(self._settings)

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["gpt-4o", "gpt-4o-mini"]

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        if llm_request.model is None:
            llm_request.model = self.model

        if self._settings.mock_mode:
            start = time.time()
            response = self._mock_response(llm_request)
            latency_ms = max(1, int((time.time() - start) * 1000))
            self._decorate_span(llm_request, response, latency_ms)
            yield response
            return

        start = time.time()
        response_payload = await asyncio.to_thread(self._call_azure, llm_request)
        latency_ms = max(1, int((time.time() - start) * 1000))
        response = self._build_llm_response(response_payload, llm_request)
        self._decorate_span(llm_request, response, latency_ms)
        yield response

    def _call_azure(self, llm_request: LlmRequest) -> dict[str, Any]:
        settings = self._settings
        endpoint = settings.azure_openai_endpoint.rstrip("/")
        deployment = settings.azure_openai_deployment
        url = (
            f"{endpoint}/openai/deployments/"
            f"{requests.utils.quote(deployment)}/chat/completions"
            f"?api-version={settings.azure_openai_api_version}"
        )

        messages = _build_messages(llm_request)
        tools = _build_tools(llm_request)

        body: dict[str, Any] = {
            "model": deployment,
            "messages": messages,
            "temperature": 1,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        headers = {"Content-Type": "application/json"}
        if settings.azure_openai_api_key:
            headers["api-key"] = settings.azure_openai_api_key
        else:
            token = _get_access_token(settings)
            headers["Authorization"] = f"Bearer {token}"

        resp = requests.post(
            url,
            headers=headers,
            json=body,
            timeout=60,
            verify=False if settings.azure_openai_skip_verify else (settings.azure_openai_ca_bundle or True),
        )
        if not resp.ok:
            detail = resp.text
            raise RuntimeError(f"Azure OpenAI error {resp.status_code}: {detail}")
        return resp.json()

    def _decorate_span(self, llm_request: LlmRequest, llm_response: LlmResponse, latency_ms: int) -> None:
        span = trace.get_current_span()
        if span is None:
            return
        span.set_attribute("llm.provider", "azure_openai")
        span.set_attribute("llm.model", llm_request.model or self.model)
        span.set_attribute("llm.latency_ms", latency_ms)

        if llm_response.usage_metadata:
            if llm_response.usage_metadata.prompt_token_count is not None:
                span.set_attribute(
                    "llm.token_usage.input",
                    llm_response.usage_metadata.prompt_token_count,
                )
            if llm_response.usage_metadata.candidates_token_count is not None:
                span.set_attribute(
                    "llm.token_usage.output",
                    llm_response.usage_metadata.candidates_token_count,
                )

    def _build_llm_response(self, payload: dict[str, Any], llm_request: LlmRequest) -> LlmResponse:
        choices = payload.get("choices", [])
        usage = payload.get("usage", {})
        if not choices:
            return LlmResponse(error_message="No choices returned")

        message = choices[0].get("message", {})
        parts: list[types.Part] = []

        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            for call in tool_calls:
                func = call.get("function", {})
                args_raw = func.get("arguments") or "{}"
                try:
                    args = json.loads(args_raw)
                except Exception:
                    args = {"raw": args_raw}
                parts.append(
                    types.Part(
                        function_call=types.FunctionCall(
                            id=call.get("id"),
                            name=func.get("name"),
                            args=args,
                        )
                    )
                )
                if func.get("name") == "transfer_to_agent":
                    self._record_a2a_span(call.get("id"), args, llm_request=llm_request)
        else:
            text = (message.get("content") or "").strip()
            parts.append(types.Part(text=text))

        usage_metadata = types.GenerateContentResponseUsageMetadata(
            prompt_token_count=usage.get("prompt_tokens"),
            candidates_token_count=usage.get("completion_tokens"),
            total_token_count=usage.get("total_tokens"),
        )
        return LlmResponse(
            content=types.Content(role="model", parts=parts),
            usage_metadata=usage_metadata,
        )

    def _mock_response(self, llm_request: LlmRequest) -> LlmResponse:
        text = _get_last_user_text(llm_request)
        agent_name = _get_agent_name(llm_request)

        if "timeout" in text and agent_name:
            raise TimeoutError("Mocked Azure OpenAI timeout")

        if _has_function_response(llm_request):
            return _mock_followup_response(llm_request, agent_name)

        if agent_name == "orchestrator":
            if "transfer_fail" in text:
                return _text_response("Routing error: transfer target unavailable.")
            if "validate" in text and "research" in text:
                self._record_a2a_span("mock-transfer", {"agent_name": "research_agent"}, llm_request)
                return _function_call_response("transfer_to_agent", {"agent_name": "research_agent"})
            if "validate" in text:
                self._record_a2a_span("mock-transfer", {"agent_name": "validator_agent"}, llm_request)
                return _function_call_response("transfer_to_agent", {"agent_name": "validator_agent"})
            if "capital" in text or "gdp" in text or "research" in text:
                self._record_a2a_span("mock-transfer", {"agent_name": "research_agent"}, llm_request)
                return _function_call_response("transfer_to_agent", {"agent_name": "research_agent"})
            return _text_response("I can route research or validation requests.")

        if agent_name == "research_agent":
            if "validate" in text:
                self._record_a2a_span("mock-transfer", {"agent_name": "validator_agent"}, llm_request)
                return _function_call_response("transfer_to_agent", {"agent_name": "validator_agent"})
            return _function_call_response("web_lookup", {"query": text or "unknown"})

        if agent_name == "validator_agent":
            if "malformed" in text:
                return _text_response("this is not json")
            if "toxic" in text:
                return _text_response("You are stupid")
            return _function_call_response("validate_data", {"value": text or ""})

        return _text_response("Unhandled agent.")

    def _record_a2a_span(self, tool_call_id: str | None, args: dict[str, Any], llm_request: LlmRequest | None) -> None:
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("a2a_delegation") as span:
            if llm_request:
                span.set_attribute("a2a.source_agent", _get_agent_name(llm_request))
            target = args.get("agent_name") or args.get("agent")
            if target:
                span.set_attribute("a2a.target_agent", target)
            if tool_call_id:
                span.set_attribute("a2a.task_id", tool_call_id)


def _build_messages(llm_request: LlmRequest) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    seen_tool_call_ids: set[str] = set()
    if llm_request.config and isinstance(llm_request.config.system_instruction, str):
        messages.append({"role": "system", "content": llm_request.config.system_instruction})

    for content in llm_request.contents:
        if not content or not content.parts:
            continue
        role = "assistant" if content.role == "model" else "user"
        text_parts = [part.text for part in content.parts if part.text]

        tool_calls_payload: list[dict[str, Any]] = []
        for part in content.parts:
            if part.function_call:
                fc = part.function_call
                tool_call_id = fc.id or f"toolcall-{int(time.time() * 1000)}"
                seen_tool_call_ids.add(tool_call_id)
                tool_calls_payload.append(
                    {
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": fc.name,
                            "arguments": json.dumps(fc.args or {}),
                        },
                    }
                )

        if tool_calls_payload:
            messages.append({"role": "assistant", "content": None, "tool_calls": tool_calls_payload})

        for part in content.parts:
            if part.function_response:
                response = part.function_response
                if response.id and response.id in seen_tool_call_ids:
                    tool_message = {
                        "role": "tool",
                        "tool_call_id": response.id,
                        "content": json.dumps(response.response or {}),
                    }
                    if response.name:
                        tool_message["name"] = response.name
                    messages.append(tool_message)
                else:
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"Tool result ({response.name or 'tool'}): "
                                f"{json.dumps(response.response or {})}"
                            ),
                        }
                    )
        if text_parts:
            messages.append({"role": role, "content": "\n".join(text_parts)})

    return messages


def _build_tools(llm_request: LlmRequest) -> list[dict[str, Any]]:
    if not llm_request.config or not llm_request.config.tools:
        return []
    tools: list[dict[str, Any]] = []
    for tool in llm_request.config.tools:
        if not tool.function_declarations:
            continue
        for decl in tool.function_declarations:
            schema = None
            if decl.parameters_json_schema:
                schema = decl.parameters_json_schema
            elif decl.parameters:
                schema = decl.parameters.model_dump(exclude_none=True, by_alias=True)
            normalized_schema = _normalize_schema_for_azure(schema or {})
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": decl.name,
                        "description": decl.description or "",
                        "parameters": normalized_schema,
                    },
                }
            )
    return tools


def _normalize_schema_for_azure(schema: Any) -> Any:
    if isinstance(schema, dict):
        normalized: dict[str, Any] = {}
        for k, v in schema.items():
            if k == "propertyOrdering":
                continue
            if k == "type" and isinstance(v, str):
                normalized[k] = _TYPE_MAP.get(v, v.lower())
            else:
                normalized[k] = _normalize_schema_for_azure(v)
        return normalized
    if isinstance(schema, list):
        return [_normalize_schema_for_azure(item) for item in schema]
    if isinstance(schema, str) and schema in _TYPE_MAP:
        return _TYPE_MAP[schema]
    return schema


def _get_last_user_text(llm_request: LlmRequest) -> str:
    for content in reversed(llm_request.contents):
        if content.role == "user" and content.parts:
            for part in content.parts:
                if part.text:
                    return part.text.lower()
    return ""


def _all_user_text(llm_request: LlmRequest) -> str:
    texts: list[str] = []
    for content in llm_request.contents:
        if content.role == "user" and content.parts:
            for part in content.parts:
                if part.text:
                    texts.append(part.text.lower())
    return "\n".join(texts)


def _get_agent_name(llm_request: LlmRequest) -> str:
    if llm_request.config and llm_request.config.labels:
        return llm_request.config.labels.get("adk_agent_name", "")
    return ""


def _has_function_response(llm_request: LlmRequest) -> bool:
    for content in reversed(llm_request.contents):
        if content.parts:
            for part in content.parts:
                if part.function_response:
                    return True
    return False


def _mock_followup_response(llm_request: LlmRequest, agent_name: str) -> LlmResponse:
    last_response = None
    for content in reversed(llm_request.contents):
        if content.parts:
            for part in content.parts:
                if part.function_response:
                    last_response = part.function_response
                    break
        if last_response:
            break

    if not last_response:
        return _text_response("No tool response.")

    if last_response.name == "web_lookup":
        result = last_response.response or {}
        all_user_text = _all_user_text(llm_request)
        if "validate" in all_user_text:
            return _function_call_response("transfer_to_agent", {"agent_name": "validator_agent"})
        if "france" in all_user_text and "capital" in all_user_text:
            return _text_response("Research result: Paris")
        if "japan" in all_user_text and "gdp" in all_user_text:
            return _text_response("Research result: Japan GDP (2023) ~ $4.2T")
        return _text_response(f"Research result: {result.get('result', '')}")

    if last_response.name == "validate_data":
        all_user_text = _all_user_text(llm_request)
        if "malformed" in all_user_text:
            return _text_response("this is not json")
        if "toxic" in all_user_text:
            return _text_response("you are stupid")
        result = last_response.response or {}
        return _text_response(json.dumps(result))

    return _text_response("Tool response processed.")


def _function_call_response(name: str, args: dict[str, Any]) -> LlmResponse:
    call = types.FunctionCall(name=name, args=args, id=f"toolcall-{int(time.time() * 1000)}")
    content = types.Content(role="model", parts=[types.Part(function_call=call)])
    usage_metadata = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=1,
        candidates_token_count=1,
        total_token_count=2,
    )
    return LlmResponse(content=content, usage_metadata=usage_metadata)


def _text_response(text: str) -> LlmResponse:
    content = types.Content(role="model", parts=[types.Part(text=text)])
    usage_metadata = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=max(1, len(text.split())),
        candidates_token_count=max(1, len(text.split())),
        total_token_count=max(2, len(text.split()) * 2),
    )
    return LlmResponse(content=content, usage_metadata=usage_metadata)
