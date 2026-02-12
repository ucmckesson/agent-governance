from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

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


class AgentRegistrationRecord(BaseModel):
    """Default BigQuery registration record schema for agents."""

    model_config = ConfigDict(extra="allow")

    agent_id: str
    env: str
    runtime: Optional[str] = None
    service_name: Optional[str] = None
    region: Optional[str] = None
    cloud_run_url: Optional[str] = None
    revision: Optional[str] = None
    version: Optional[str] = None
    owner: Optional[str] = None
    tools: list[str] = Field(default_factory=list)
    datasources: list[str] = Field(default_factory=list)
    write_tools: list[str] = Field(default_factory=list)
    last_deploy_times: list[datetime] = Field(default_factory=list)
    status: Optional[str] = None


def default_registration_schema() -> list[Dict[str, str]]:
    """Default BigQuery schema for agent registration table."""
    return [
        {"name": "agent_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "env", "type": "STRING", "mode": "REQUIRED"},
        {"name": "runtime", "type": "STRING", "mode": "NULLABLE"},
        {"name": "service_name", "type": "STRING", "mode": "NULLABLE"},
        {"name": "region", "type": "STRING", "mode": "NULLABLE"},
        {"name": "cloud_run_url", "type": "STRING", "mode": "NULLABLE"},
        {"name": "revision", "type": "STRING", "mode": "NULLABLE"},
        {"name": "version", "type": "STRING", "mode": "NULLABLE"},
        {"name": "owner", "type": "STRING", "mode": "NULLABLE"},
        {"name": "tools", "type": "STRING", "mode": "REPEATED"},
        {"name": "datasources", "type": "STRING", "mode": "REPEATED"},
        {"name": "write_tools", "type": "STRING", "mode": "REPEATED"},
        {"name": "last_deploy_times", "type": "TIMESTAMP", "mode": "REPEATED"},
        {"name": "status", "type": "STRING", "mode": "NULLABLE"},
    ]
