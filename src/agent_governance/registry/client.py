from __future__ import annotations

from typing import Any, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..exceptions import RegistryError
from .cache import RegistryCache
from .models import RegistryAgent


class RegistryClient:
    def __init__(self, base_url: str, timeout_s: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_s
        self.cache = RegistryCache()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4))
    def get_agent(self, agent_id: str) -> RegistryAgent:
        cached = self.cache.get(agent_id)
        if cached:
            return cached
        try:
            url = f"{self.base_url}/agents/{agent_id}"
            resp = httpx.get(url, timeout=self.timeout)
            resp.raise_for_status()
            model = RegistryAgent.model_validate(resp.json())
            self.cache.set(agent_id, model)
            return model
        except Exception as exc:
            raise RegistryError(str(exc)) from exc

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4))
    def upsert_agent(self, payload: Dict[str, Any]) -> RegistryAgent:
        try:
            url = f"{self.base_url}/agents"
            resp = httpx.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            model = RegistryAgent.model_validate(resp.json())
            self.cache.set(model.agent_id, model)
            return model
        except Exception as exc:
            raise RegistryError(str(exc)) from exc
