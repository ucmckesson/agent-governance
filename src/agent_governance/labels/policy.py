from __future__ import annotations

from typing import Iterable, Set


class LabelPolicy:
    def __init__(self, required: Iterable[str] | None = None) -> None:
        self.required: Set[str] = set(required or [])
