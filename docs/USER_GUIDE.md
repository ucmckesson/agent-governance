# Agent Governance SDK User Guide

This guide is for teams evaluating or onboarding the SDK.

## 1) What users should receive

For a clean handoff, share:

- package install command
- one minimal `governance.yaml`
- one runnable integration example (ADK or API)
- one test command
- one observability check command (Cloud Logging or local JSONL)

## 2) Install

From repo root:

- `pip install -e .`

Or from GitHub tag:

- `pip install git+https://github.com/ucmckesson/agent-governance.git@v0.1.1`

Optional extras:

- telemetry: `pip install -e .[telemetry]`
- tracing: `pip install -e .[tracing]`
- registry: `pip install -e .[registry]`
- test: `pip install -e .[test]`

## 3) Minimal configuration

Create `governance.yaml`:

```yaml
agent:
  agent_id: my-agent
  agent_name: My Agent
  agent_type: adk
  version: "1.0.0"
  env: dev
  gcp_project: my-project

telemetry:
  enabled: true
  redaction_keys: ["authorization", "token", "secret"]
  buffer_size: 100

guardrails:
  policy_file: "guardrails.yaml"
  model_schema_file: "model_schema.yaml"
```

## 4) Fastest production bootstrap

Use one call:

```python
from agent_governance import init_governance

runtime = init_governance("governance.yaml")

# ready to use
logger = runtime.logger
governance = runtime.middleware
lifecycle = runtime.lifecycle
```

This initializes runtime detection, telemetry, middleware, registration, and heartbeat.

## 5) ADK usage pattern

```python
async def handle_request(user_input: str, user_id: str):
    processed_input, ctx, start_time = await governance.before_agent_call(
        governance.agent, user_input, user_id=user_id
    )

    # invoke your ADK agent with processed_input
    output = "..."

    return await governance.after_agent_call(
        governance.agent, ctx, output, start_time
    )
```

Tool wrapping pattern:

```python
tool_params = await governance.before_tool_call(
    governance.agent, ctx, "crm_search", {"query": "status"}
)

result = {"status": "ok"}

await governance.after_tool_call(
    governance.agent, ctx, "crm_search", result, latency_ms=12, success=True
)
```

## 6) Shutdown handling (important)

On service shutdown, emit stopped status and stop heartbeat:

```python
lifecycle.stop_heartbeat()
lifecycle.mark_stopped()
```

If your service detects failure state:

```python
lifecycle.mark_unhealthy("dependency timeout")
```

## 7) How to test quickly

Run package tests:

- `python -m pytest -q`

Run ADK integration harness:

- see [adk-multiagent-test/README.md](../adk-multiagent-test/README.md)

## 8) What to verify in logs

Check for these event families:

- `registration_event` (`started`, `healthy`, `stopped`, `unhealthy`)
- `agent_request_start` / `agent_request_end`
- tool call events
- policy/guardrail outcomes

In GCP runtimes, Cloud Logging is auto-enabled when telemetry cloud settings are not explicitly configured.

## 9) Related docs

- [docs/CUSTOMER_QUICKSTART.md](CUSTOMER_QUICKSTART.md)
- [README.md](../README.md)
- [docs/ADK_USER_GUIDE.md](ADK_USER_GUIDE.md)
- [docs/ADK_E2E_GUIDE.md](ADK_E2E_GUIDE.md)
- [docs/REFERENCE_ARCHITECTURE.md](REFERENCE_ARCHITECTURE.md)