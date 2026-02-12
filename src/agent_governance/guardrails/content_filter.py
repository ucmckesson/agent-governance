from __future__ import annotations

from typing import Iterable


class ContentFilter:
    def __init__(self, blocklist: Iterable[str] | None = None) -> None:
        self.blocklist = [item.lower() for item in (blocklist or [])]

    def is_safe(self, text: str) -> bool:
        lower = text.lower()
        return not any(bad in lower for bad in self.blocklist)
