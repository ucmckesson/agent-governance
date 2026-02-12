from __future__ import annotations

from typing import Dict

from .policy import LabelPolicy


class LabelValidator:
    def __init__(self, policy: LabelPolicy) -> None:
        self.policy = policy

    def validate(self, labels: Dict[str, str]) -> tuple[bool, list[str]]:
        missing = [key for key in self.policy.required if key not in labels]
        return len(missing) == 0, missing
