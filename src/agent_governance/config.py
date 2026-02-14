from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from importlib import resources

import yaml
from pydantic import BaseModel, Field

from .constants import DEFAULT_CONFIG_PATH, ENV_PREFIX
from .exceptions import ConfigError
from .models import GovernanceConfigModel
from .registry.models import default_registration_schema


class GovernanceConfig(BaseModel):
    """Parsed governance configuration with helpers."""

    raw: GovernanceConfigModel
    path: Path = Field(default_factory=lambda: Path(DEFAULT_CONFIG_PATH))

    @property
    def agent(self):
        return self.raw.agent

    def section(self, name: str) -> Dict[str, Any]:
        return getattr(self.raw, name, {}) or {}


def _apply_env_overrides(data: Dict[str, Any], prefix: str) -> Dict[str, Any]:
    """Apply GOV_* overrides using __ to represent nested keys."""

    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        path = key[len(prefix) :].lower().split("__")
        cursor = data
        for part in path[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[path[-1]] = _coerce_value(value)
    return data


def _default_guardrails_policy() -> Dict[str, Any]:
    try:
        text = resources.files("agent_governance.guardrails").joinpath("default_guardrails.yaml").read_text()
        return yaml.safe_load(text) or {}
    except Exception:
        return {}


def _guardrails_profile_defaults(profile: str) -> Dict[str, Any]:
    profile = (profile or "strict").lower()

    if profile == "custom":
        return {}

    if profile == "strict":
        return {
            "enabled": True,
            "input_validation": {"block_known_injection_patterns": True},
            "content_safety": {
                "enabled": True,
                "block_categories": ["harassment", "hate_speech", "violence", "self_harm", "sexual_content"],
                "topic_blocklist": ["illegal_acts", "sexual_content", "competitor_data", "PII_extraction"],
            },
            "tools": {
                "default_policy": {"allowed": False},
                "policies": [
                    {"tool_name": "search_internal_kb", "allowed": True},
                    {"tool_name": "read_read_only_db", "allowed": True},
                    {"tool_name": "execute_shell", "allowed": False},
                    {"tool_name": "delete_file", "allowed": False},
                    {"tool_name": "write_to_prod_db", "allowed": False},
                    {"tool_name": "email_user", "allowed": True, "requires_confirmation": True},
                    {"tool_name": "update_customer_record", "allowed": True, "requires_confirmation": True},
                ],
            },
            "rate_limiting": {
                "enabled": True,
                "requests_per_minute_per_user": 10,
                "requests_per_minute_global": 10,
            },
        }

    if profile == "balanced":
        return {
            "enabled": True,
            "input_validation": {"block_known_injection_patterns": True},
            "content_safety": {
                "enabled": True,
                "block_categories": ["harassment", "hate_speech", "violence", "self_harm"],
            },
            "tools": {
                "default_policy": {"allowed": True},
            },
            "rate_limiting": {
                "enabled": True,
                "requests_per_minute_per_user": 60,
                "requests_per_minute_global": 300,
            },
        }

    if profile == "permissive":
        return {
            "enabled": True,
            "input_validation": {"block_known_injection_patterns": False},
            "content_safety": {
                "enabled": True,
                "block_categories": [],
            },
            "tools": {
                "default_policy": {"allowed": True},
            },
            "rate_limiting": {
                "enabled": True,
                "requests_per_minute_per_user": 300,
                "requests_per_minute_global": 1000,
            },
        }

    raise ConfigError(f"Unsupported guardrails profile: {profile}")


def _normalize_guardrails_policy(policy: Dict[str, Any]) -> Dict[str, Any]:
    if not policy:
        return {}
    if not any(key in policy for key in ["input_guardrails", "output_guardrails", "action_guardrails", "rate_limits"]):
        return policy

    normalized: Dict[str, Any] = {"enabled": True}
    tools_cfg: Dict[str, Any] = {"default_policy": {"allowed": False}, "policies": []}
    input_validation: Dict[str, Any] = {}
    output_validation: Dict[str, Any] = {}
    content_safety: Dict[str, Any] = {"enabled": True, "block_categories": []}
    rate_limiting: Dict[str, Any] = {"enabled": True}
    topic_blocklist: list[str] = []

    for rule in policy.get("input_guardrails", []) or []:
        if rule.get("type") == "prompt_injection":
            input_validation["block_known_injection_patterns"] = True
        if rule.get("type") == "topic_filter":
            topic_blocklist.extend(rule.get("disallowed_topics", []) or [])

    for rule in policy.get("output_guardrails", []) or []:
        if rule.get("type") == "content_safety":
            content_safety["block_categories"] = [
                "harassment",
                "hate_speech",
                "violence",
                "self_harm",
                "sexual_content",
            ]

    for rule in policy.get("action_guardrails", []) or []:
        if rule.get("type") == "tool_authorization":
            for tool_name in rule.get("allowed_tools", []) or []:
                tools_cfg["policies"].append({"tool_name": tool_name, "allowed": True})
            for tool_name in rule.get("disallowed_tools", []) or []:
                tools_cfg["policies"].append({"tool_name": tool_name, "allowed": False})
        if rule.get("type") == "approval_gate":
            for tool_name in rule.get("actions", []) or []:
                tools_cfg["policies"].append({"tool_name": tool_name, "allowed": True, "requires_confirmation": True})

    rate_limits = policy.get("rate_limits", {})
    if rate_limits:
        max_rpm = int(rate_limits.get("max_requests_per_minute", 10))
        rate_limiting["requests_per_minute_per_user"] = max_rpm
        rate_limiting["requests_per_minute_global"] = max_rpm

    if topic_blocklist:
        content_safety["topic_blocklist"] = topic_blocklist

    normalized["tools"] = tools_cfg
    if input_validation:
        normalized["input_validation"] = input_validation
    if output_validation:
        normalized["output_validation"] = output_validation
    normalized["content_safety"] = content_safety
    normalized["rate_limiting"] = rate_limiting
    return normalized


def _apply_dlp_from_guardrails(data: Dict[str, Any], policy: Dict[str, Any]) -> None:
    dlp_cfg = data.get("dlp") or {}
    info_types: set[str] = set(dlp_cfg.get("info_types", []) or [])

    def _apply_action(action_key: str, action_value: str) -> None:
        if action_key not in dlp_cfg:
            dlp_cfg[action_key] = action_value

    for rule in policy.get("input_guardrails", []) or []:
        if rule.get("type") == "pii_redaction":
            info_types.update(rule.get("entities", []) or [])
            _apply_action("action_on_input_pii", rule.get("action", "redact"))
            dlp_cfg.setdefault("scan_input", True)

    for rule in policy.get("output_guardrails", []) or []:
        if rule.get("type") == "pii_redaction":
            info_types.update(rule.get("entities", []) or [])
            _apply_action("action_on_output_pii", rule.get("action", "redact"))
            dlp_cfg.setdefault("scan_output", True)

    if info_types:
        dlp_cfg.setdefault("enabled", True)
        dlp_cfg["info_types"] = sorted(info_types)
        data["dlp"] = dlp_cfg


def _coerce_value(value: str) -> Any:
    lower = value.lower()
    if lower in {"true", "false"}:
        return lower == "true"
    if lower in {"null", "none"}:
        return None
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def load_config(
    path: Optional[str | Path] = None,
    env_prefix: str = ENV_PREFIX,
    guardrails_path: Optional[str | Path] = None,
) -> GovernanceConfig:
    config_path = Path(path or os.getenv("GOVERNANCE_CONFIG_PATH") or DEFAULT_CONFIG_PATH)
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    try:
        raw_data = yaml.safe_load(config_path.read_text()) or {}
    except Exception as exc:  # pragma: no cover - defensive
        raise ConfigError(f"Failed to parse config: {exc}") from exc

    if not isinstance(raw_data, dict):
        raise ConfigError("governance.yaml must be a YAML mapping")

    data = _apply_env_overrides(raw_data, env_prefix)

    if "guardrails" not in data or data.get("guardrails") is None:
        data["guardrails"] = _default_guardrails_policy()

    if isinstance(data.get("guardrails"), dict):
        profile = str(data["guardrails"].get("profile", "strict")).lower()
        profile_defaults = _guardrails_profile_defaults(profile)
        if profile_defaults:
            data["guardrails"] = _deep_merge(profile_defaults, data["guardrails"])
        data["guardrails"] = _normalize_guardrails_policy(data["guardrails"])

    guardrails_cfg = data.get("guardrails") or {}
    policy_file = guardrails_path or guardrails_cfg.get("policy_file") or guardrails_cfg.get("policy_path")
    if policy_file:
        policy_path = Path(policy_file)
        policy_data = yaml.safe_load(policy_path.read_text()) or {}
        policy_data = _normalize_guardrails_policy(policy_data)
        _apply_dlp_from_guardrails(data, policy_data)
        data["guardrails"] = _deep_merge(guardrails_cfg, policy_data)
    else:
        _apply_dlp_from_guardrails(data, guardrails_cfg)

    registry_cfg = data.get("registry") or {}
    registry_cfg.setdefault("registration_schema", default_registration_schema())
    data["registry"] = registry_cfg

    try:
        model = GovernanceConfigModel.model_validate(data)
    except Exception as exc:
        raise ConfigError(f"Invalid config: {exc}") from exc

    return GovernanceConfig(raw=model, path=config_path)
