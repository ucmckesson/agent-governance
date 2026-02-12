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
