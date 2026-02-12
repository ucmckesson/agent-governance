from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple


class RegistryCache:
    def __init__(self, ttl_seconds: int = 300) -> None:
        self.ttl = timedelta(seconds=ttl_seconds)
        self._cache: Dict[str, Tuple[datetime, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        item = self._cache.get(key)
        if not item:
            return None
        ts, value = item
        if datetime.utcnow() - ts > self.ttl:
            self._cache.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._cache[key] = (datetime.utcnow(), value)
