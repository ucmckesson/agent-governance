# ADK Multi-Agent Test Harness

Implements A2A + Guardrails + OTel observability using Azure OpenAI.

## Setup

- Copy `.env.example` to `.env` and fill values
- Install deps: `python -m pip install -e .`

By default `AZURE_OPENAI_MOCK=true` runs a local mock model for tests and demos.

## Run demo

`python scripts/run_demo.py`

## Run Azure ADK + OTel + A2A validation

1. Set `AZURE_OPENAI_MOCK=false` in `.env`
2. Fill Azure values in `.env` (`AZURE_OPENAI_ENDPOINT`, auth fields, deployment, API version)
3. Run: `python scripts/run_azure_adk_otel_e2e.py`

This script:
- runs multi-agent queries through ADK
- prints A2A transfer targets per query
- prints summarized OTel span counts
- writes Cloud Logging JSONL output to `artifacts/spans.cloudlogging.jsonl`

## Optional Jaeger

`docker compose up -d`

## Cloud Run production-style test (GitHub Actions)

- Cloud Run app: `deploy/cloud_run/main.py`
- Config: `deploy/cloud_run/governance.yaml`
- Dockerfile: `deploy/cloud_run/Dockerfile`
- Workflow template: `../examples/github_actions/cloudrun_adk_multiagent_prod_test.yaml`

Copy the workflow template into `.github/workflows/` in your repo and follow
the setup in [docs/CLOUD_RUN_GITHUB_ACTIONS_GUIDE.md](../docs/CLOUD_RUN_GITHUB_ACTIONS_GUIDE.md).

## Tests

`pytest -q`
