class GovernanceError(Exception):
    """Base class for all SDK exceptions."""


class ConfigError(GovernanceError):
    """Configuration loading/validation errors."""


class TelemetryError(GovernanceError):
    """Telemetry system errors."""


class GuardrailError(GovernanceError):
    """Guardrails enforcement errors."""


class DLPError(GovernanceError):
    """DLP scanner errors."""


class RegistryError(GovernanceError):
    """Registry client errors."""


class EvalError(GovernanceError):
    """Evaluation harness errors."""


class ComplianceError(GovernanceError):
    """Compliance checking errors."""


class InputBlockedError(GovernanceError):
    """User input was blocked by guardrails."""


class ToolBlockedError(GovernanceError):
    """Tool call was blocked by guardrails."""


class OutputBlockedError(GovernanceError):
    """Agent output was blocked by guardrails."""
