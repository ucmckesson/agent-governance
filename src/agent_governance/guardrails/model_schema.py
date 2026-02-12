from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from jsonschema import Draft202012Validator


class ModelSchemaValidator:
    """Validates input/output/tool params using JSON Schema loaded from YAML."""

    def __init__(self, schema_path: str | Path | None = None, schema: Optional[Dict[str, Any]] = None) -> None:
        self._schema = schema or (self._load(schema_path) if schema_path else {})
        self._input_validator = self._make_validator(self._schema.get("input_schema"))
        self._output_validator = self._make_validator(self._schema.get("output_schema"))
        self._tool_validators: Dict[str, Draft202012Validator] = {}
        tool_params = self._schema.get("tool_params", {}) or {}
        for tool_name, spec in tool_params.items():
            validator = self._make_validator(spec.get("schema") if isinstance(spec, dict) else spec)
            if validator:
                self._tool_validators[tool_name] = validator

    @staticmethod
    def _load(path: str | Path) -> Dict[str, Any]:
        data = yaml.safe_load(Path(path).read_text())
        return data or {}

    @staticmethod
    def _make_validator(schema: Optional[Dict[str, Any]]) -> Optional[Draft202012Validator]:
        if not schema:
            return None
        return Draft202012Validator(schema)

    def validate_input(self, payload: Any) -> list[str]:
        if not self._input_validator:
            return []
        return [e.message for e in self._input_validator.iter_errors(payload)]

    def validate_output(self, payload: Any) -> list[str]:
        if not self._output_validator:
            return []
        return [e.message for e in self._output_validator.iter_errors(payload)]

    def validate_tool_params(self, tool_name: str, payload: Any) -> list[str]:
        validator = self._tool_validators.get(tool_name)
        if not validator:
            return []
        return [e.message for e in validator.iter_errors(payload)]
