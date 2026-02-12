"""Shared data models for the agent_governance_sdk."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class Environment(str, Enum):
    DEV = "dev"
    STAGING = "staging"
    PRODUCTION = "prod"


class RiskTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DataClassification(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class LifecycleStatus(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"
    DECOMMISSIONED = "decommissioned"


class EvalVerdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    SKIP = "skip"


class ComplianceStatus(str, Enum):
    COMPLIANT = "compliant"
    REVIEW_NEEDED = "review_needed"
    NON_COMPLIANT = "non_compliant"
    EXEMPT = "exempt"


class GuardrailAction(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    REDACT = "redact"
    WARN = "warn"
    CONFIRM = "confirm"


class EventType(str, Enum):
    AGENT_REQUEST_START = "agent_request_start"
    AGENT_REQUEST_END = "agent_request_end"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_END = "tool_call_end"
    SAFETY_EVENT = "safety_event"
    DLP_EVENT = "dlp_event"
    GUARDRAIL_EVENT = "guardrail_event"
    EVAL_EVENT = "eval_event"
    ERROR_EVENT = "error_event"


class AgentType(str, Enum):
    ADK = "adk"
    AGENT_BUILDER = "agent_builder"
    VERTEX_ENDPOINT = "vertex_endpoint"
    CUSTOM = "custom"


class DLPAction(str, Enum):
    BLOCK = "block"
    REDACT = "redact"
    LOG_ONLY = "log"


class AgentIdentity(BaseModel):
    agent_id: str
    agent_name: str
    agent_type: AgentType
    version: str
    env: Environment
    gcp_project: str
    region: str = "us-central1"
    service_account: Optional[str] = None

    @property
    def deployment_key(self) -> str:
        return f"{self.agent_id}:{self.env.value}:{self.version}"


class RequestContext(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    user_id_hash: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @staticmethod
    def hash_user_id(raw_user_id: str) -> str:
        return hashlib.sha256(raw_user_id.encode()).hexdigest()[:16]


class BaseEvent(BaseModel):
    event_type: EventType
    agent: AgentIdentity
    context: RequestContext
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    attributes: Dict[str, Any] = Field(default_factory=dict)


class GuardrailResult(BaseModel):
    action: GuardrailAction
    rule_name: str = ""
    reason: str
    details: Dict[str, Any] = Field(default_factory=dict)


class DLPFinding(BaseModel):
    info_type: str
    quote: Optional[str] = None
    likelihood: Optional[str] = None


class DLPScanResult(BaseModel):
    action: DLPAction
    findings: List[DLPFinding] = Field(default_factory=list)
    redacted_text: Optional[str] = None


class RegistryRecord(BaseModel):
    agent_id: str
    agent_name: str
    owner: str
    risk_tier: RiskTier
    data_classification: DataClassification
    lifecycle: LifecycleStatus
    last_eval_at: Optional[datetime] = None
    labels: Dict[str, str] = Field(default_factory=dict)


class EvalMetricResult(BaseModel):
    name: str
    value: float
    verdict: EvalVerdict
    threshold: Optional[float] = None


class EvalRunResult(BaseModel):
    agent_id: str
    started_at: datetime
    finished_at: datetime
    metrics: List[EvalMetricResult]
    overall: EvalVerdict


class ComplianceCheckResult(BaseModel):
    name: str
    status: ComplianceStatus
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ComplianceReport(BaseModel):
    agent_id: str
    generated_at: datetime
    status: ComplianceStatus
    checks: List[ComplianceCheckResult]


class GovernanceConfigModel(BaseModel):
    agent: AgentIdentity
    telemetry: Dict[str, Any] = Field(default_factory=dict)
    guardrails: Dict[str, Any] = Field(default_factory=dict)
    dlp: Dict[str, Any] = Field(default_factory=dict)
    registry: Dict[str, Any] = Field(default_factory=dict)
    eval: Dict[str, Any] = Field(default_factory=dict)
    compliance: Dict[str, Any] = Field(default_factory=dict)
    labels: Dict[str, Any] = Field(default_factory=dict)
    golden_data: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("telemetry", "guardrails", "dlp", "registry", "eval", "compliance", "labels", "golden_data")
    @classmethod
    def _default_dict(cls, value: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return value or {}
