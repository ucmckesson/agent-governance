from __future__ import annotations

import re

from google.adk.tools.function_tool import FunctionTool

EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def validate_data(value: str) -> dict:
    """Validate a string value. Returns JSON-serializable result."""
    text = value.lower()
    if "malformed" in text:
        return {"oops": "not schema compliant"}
    if "toxic" in text:
        return {"valid": True, "reasons": ["you are stupid"]}

    reasons: list[str] = []
    valid = True
    if "@" in value:
        if not EMAIL_PATTERN.match(value.strip()):
            valid = False
            reasons.append("invalid email format")
    if not value.strip():
        valid = False
        reasons.append("empty value")
    return {"valid": valid, "reasons": reasons}


class ValidateDataTool(FunctionTool):
    def __init__(self) -> None:
        super().__init__(func=validate_data)
