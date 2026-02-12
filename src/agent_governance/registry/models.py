from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel

from ..models import DataClassification, LifecycleStatus, RiskTier


class RegistryAgent(BaseModel):
    agent_id: str
    agent_name: str
    owner: str
    risk_tier: RiskTier
    data_classification: DataClassification
    lifecycle: LifecycleStatus
    labels: Dict[str, str] = {}
    last_eval_at: Optional[datetime] = None
