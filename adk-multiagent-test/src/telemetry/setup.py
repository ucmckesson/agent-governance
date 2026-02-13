from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


_EXPORTER: InMemorySpanExporter | None = None
_INITIALIZED = False


def setup_telemetry(use_console: bool = False) -> InMemorySpanExporter:
    global _EXPORTER, _INITIALIZED
    if _EXPORTER is None:
        _EXPORTER = InMemorySpanExporter()

    if not _INITIALIZED:
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(_EXPORTER))
        if use_console:
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(provider)
        _INITIALIZED = True

    return _EXPORTER
