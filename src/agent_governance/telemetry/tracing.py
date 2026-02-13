from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from opentelemetry import trace

from .instrumentation import auto_instrument_httpx

logger = logging.getLogger(__name__)

_initialized = False
_tracer: Optional[trace.Tracer] = None


def init_tracing(agent, telemetry_cfg: Dict[str, Any]) -> trace.Tracer:
    global _initialized, _tracer
    if _initialized and _tracer is not None:
        return _tracer

    tracing_cfg = telemetry_cfg.get("tracing", {})
    enabled = tracing_cfg.get("enabled", False) or telemetry_cfg.get("tracing_enabled", False)
    if not enabled:
        _tracer = trace.get_tracer("agent_governance")
        _initialized = True
        return _tracer

    if not _otel_sdk_available():
        logger.info("OpenTelemetry SDK not installed. Tracing disabled.")
        _tracer = trace.get_tracer("agent_governance")
        _initialized = True
        return _tracer

    _tracer = _configure_otel(agent, tracing_cfg)
    _initialized = True
    return _tracer


def get_tracer() -> trace.Tracer:
    return _tracer or trace.get_tracer("agent_governance")


def shutdown_tracing() -> None:
    try:
        from opentelemetry.sdk.trace import TracerProvider

        provider = trace.get_tracer_provider()
        if isinstance(provider, TracerProvider):
            provider.shutdown()
    except Exception:
        pass


def _otel_sdk_available() -> bool:
    try:
        from opentelemetry.sdk.trace import TracerProvider  # noqa: F401

        return True
    except Exception:
        return False


def _configure_otel(agent, tracing_cfg: Dict[str, Any]) -> trace.Tracer:
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio
    from opentelemetry.propagate import set_global_textmap

    resource = Resource.create(
        {
            SERVICE_NAME: agent.agent_id,
            SERVICE_VERSION: agent.version,
            "deployment.environment": agent.env.value if hasattr(agent.env, "value") else agent.env,
            "cloud.provider": "gcp",
            "cloud.platform": "gcp_cloud_run",
            "cloud.region": getattr(agent, "region", "") or "",
            "cloud.account.id": getattr(agent, "gcp_project", "") or "",
            "governance.agent_id": agent.agent_id,
            "governance.agent_type": getattr(agent, "agent_type", ""),
        }
    )

    sample_rate = float(tracing_cfg.get("sample_rate", 1.0))
    provider = TracerProvider(resource=resource, sampler=ParentBasedTraceIdRatio(sample_rate))

    exporter = _create_exporter()
    if tracing_cfg.get("dev_console", False):
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    try:
        from opentelemetry.propagators.gcp import CloudTraceFormatPropagator

        set_global_textmap(CloudTraceFormatPropagator())
    except Exception:
        pass
    auto_instrument_httpx()

    return trace.get_tracer("agent_governance")


def _create_exporter():
    try:
        from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter

        return CloudTraceSpanExporter()
    except Exception:
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter

        return ConsoleSpanExporter()
