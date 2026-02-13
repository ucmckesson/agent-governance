# ADK End-to-End Test Guide

This test runs ADK integration + telemetry + guardrails + OTel spans in one flow.

## Prereqs

- Install the SDK with tracing extras (so spans are exported):
  - agent-governance-sdk[tracing]

## Run

From repo root:

- source .venv/bin/activate
- python tests/adk_otel_e2e_demo.py

## What you should see

- Structured logs with `agent_request_start`/`agent_request_end`
- Redacted input (email/phone)
- Tool call blocked by guardrails
- If OTel SDK is present, spans emitted (console exporter in dev)
