from __future__ import annotations

from typing import Iterable


class ToolPolicy:
    def __init__(self, allowlist: Iterable[str] | None = None, denylist: Iterable[str] | None = None) -> None:
        self.allowlist = set(allowlist or [])
        self.denylist = set(denylist or [])

    def is_allowed(self, tool_name: str) -> bool:
        if tool_name in self.denylist:
            return False
        if not self.allowlist:
            return True
        return tool_name in self.allowlist
