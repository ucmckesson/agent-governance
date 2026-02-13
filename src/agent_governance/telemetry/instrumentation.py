from __future__ import annotations


def auto_instrument_httpx() -> None:
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
    except Exception:
        pass
