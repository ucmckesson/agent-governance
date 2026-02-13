# Customer Quickstart (1 Page)

Use this when onboarding a new team to the SDK.

## Goal

Get governance running in under 15 minutes with:

- install
- minimal config
- one-call bootstrap
- smoke test
- log verification

## 1) Install

```bash
pip install git+https://github.com/ucmckesson/agent-governance.git@v0.1.1
```

Or for local evaluation:

```bash
pip install -e .
```

## 2) Create governance.yaml

```yaml
agent:
  agent_id: customer-agent
  agent_name: Customer Agent
  agent_type: adk
  version: "1.0.0"
  env: dev
  gcp_project: my-project

telemetry:
  enabled: true
  redaction_keys: ["authorization", "token", "secret"]

guardrails:
  policy_file: "guardrails.yaml"
  model_schema_file: "model_schema.yaml"
```

## 3) Bootstrap in code

```python
from agent_governance import init_governance

runtime = init_governance("governance.yaml")
governance = runtime.middleware
```

Use `governance.before_agent_call()` and `governance.after_agent_call()` around your ADK execution.

## 4) Shutdown hooks

```python
runtime.lifecycle.stop_heartbeat()
runtime.lifecycle.mark_stopped()
```

## 5) Smoke test

```bash
python -m pytest -q
```

If using the integration harness:

```bash
cd adk-multiagent-test
../.venv/bin/python scripts/run_azure_adk_otel_e2e.py
```

## 6) Verify expected events

Look for:

- `registration_event` (`started`, `healthy`, `stopped`)
- `agent_request_start`
- `agent_request_end`
- tool call events

In Cloud Run/GCP runtime, Cloud Logging is auto-enabled unless explicitly overridden.

## 7) Next docs

- [User Guide](USER_GUIDE.md)
- [ADK User Guide](ADK_USER_GUIDE.md)
- [ADK E2E Guide](ADK_E2E_GUIDE.md)
- [Reference Architecture](REFERENCE_ARCHITECTURE.md)