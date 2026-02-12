from __future__ import annotations

from typing import Dict, Iterable, List


def generate_synthetic_cases(prompts: Iterable[str]) -> List[Dict[str, str]]:
    return [{"prompt": prompt, "expected": ""} for prompt in prompts]
