from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, Field

from .constants import DEFAULT_CONFIG_PATH, ENV_PREFIX
from .exceptions import ConfigError
from .models import GovernanceConfigModel


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


def load_config(path: Optional[str | Path] = None, env_prefix: str = ENV_PREFIX) -> GovernanceConfig:
    config_path = Path(path or DEFAULT_CONFIG_PATH)
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    try:
        raw_data = yaml.safe_load(config_path.read_text()) or {}
    except Exception as exc:  # pragma: no cover - defensive
        raise ConfigError(f"Failed to parse config: {exc}") from exc

    if not isinstance(raw_data, dict):
        raise ConfigError("governance.yaml must be a YAML mapping")

    data = _apply_env_overrides(raw_data, env_prefix)

    try:
        model = GovernanceConfigModel.model_validate(data)
    except Exception as exc:
        raise ConfigError(f"Invalid config: {exc}") from exc

    return GovernanceConfig(raw=model, path=config_path)
