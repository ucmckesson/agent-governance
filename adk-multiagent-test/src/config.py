from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Iterable
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


@dataclass(frozen=True)
class Settings:
    azure_openai_endpoint: str
    azure_openai_api_key: str | None
    azure_openai_token_url: str | None
    azure_openai_client_id: str | None
    azure_openai_client_secret: str | None
    azure_openai_scope: str | None
    azure_openai_deployment: str
    azure_openai_api_version: str
    azure_openai_ca_bundle: str | None
    azure_openai_skip_verify: bool

    orchestrator_model: str
    research_model: str
    validator_model: str

    banned_topics: list[str]
    toxicity_regex: str
    mock_mode: bool


_SETTINGS: Settings | None = None


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def get_settings() -> Settings:
    global _SETTINGS
    if _SETTINGS is not None:
        return _SETTINGS

    _SETTINGS = Settings(
        azure_openai_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/"),
        azure_openai_api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
        azure_openai_token_url=os.environ.get("AZURE_OPENAI_TOKEN_URL"),
        azure_openai_client_id=os.environ.get("AZURE_OPENAI_CLIENT_ID")
        or os.environ.get("CLIENT_ID"),
        azure_openai_client_secret=os.environ.get("AZURE_OPENAI_CLIENT_SECRET")
        or os.environ.get("CLIENT_SECRET"),
        azure_openai_scope=os.environ.get("AZURE_OPENAI_SCOPE"),
        azure_openai_deployment=(
            os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
            or os.environ.get("OPENAI_MODEL")
            or os.environ.get("AZURE_OPENAI_MODEL")
            or "gpt-4o"
        ),
        azure_openai_api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-06-01"),
        azure_openai_ca_bundle=os.environ.get("AZURE_OPENAI_CA_BUNDLE"),
        azure_openai_skip_verify=os.environ.get("AZURE_OPENAI_SKIP_VERIFY", "false").lower()
        in {"1", "true", "yes"},
        orchestrator_model=os.environ.get("AZURE_OPENAI_ORCHESTRATOR_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or "gpt-4o",
        research_model=os.environ.get("AZURE_OPENAI_RESEARCH_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or "gpt-4o-mini",
        validator_model=os.environ.get("AZURE_OPENAI_VALIDATOR_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or "gpt-4o-mini",
        banned_topics=_split_csv(os.environ.get("BANNED_TOPICS")),
        toxicity_regex=os.environ.get("TOXICITY_REGEX", r"\b(hate|stupid|idiot)\b"),
        mock_mode=os.environ.get("AZURE_OPENAI_MOCK", "true").lower() in {"1", "true", "yes"},
    )
    return _SETTINGS


def ensure_settings_valid(settings: Settings) -> None:
    if settings.mock_mode:
        return
    if not settings.azure_openai_endpoint:
        raise ValueError("AZURE_OPENAI_ENDPOINT is required unless AZURE_OPENAI_MOCK=true")
    if not settings.azure_openai_api_key and not settings.azure_openai_token_url:
        raise ValueError(
            "AZURE_OPENAI_API_KEY or AZURE_OPENAI_TOKEN_URL is required unless AZURE_OPENAI_MOCK=true"
        )


def iter_banned_topics(settings: Settings) -> Iterable[str]:
    for topic in settings.banned_topics:
        if topic:
            yield topic
