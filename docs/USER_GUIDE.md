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

Recommended app repo structure:

```text
my-agent-app/
  src/
    app.py
  governance.yaml
  guardrails.yaml
  model_schema.yaml
```

Alternative structure with a config folder:

```text
my-agent-app/
  src/
    app.py
  config/
    governance.yaml
    guardrails.yaml
    model_schema.yaml
```

If you use `config/`, initialize with `init_governance("config/governance.yaml")`.

Default behavior when files are omitted:

- `governance.yaml` is required (package needs a base config file).
- if `guardrails.policy_file` is not set, package uses built-in default policy:
  - `src/agent_governance/guardrails/default_guardrails.yaml`
- if `model_schema_file` is not set, schema validation is skipped.
- if `telemetry.cloud_logging` is not explicitly set and runtime is GCP, Cloud Logging is auto-enabled.

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
  profile: strict   # strict | balanced | permissive | custom
  policy_file: "guardrails.yaml"
  model_schema_file: "model_schema.yaml"
```

Profile behavior:

- `strict`: strongest defaults (recommended for production)
- `balanced`: safer defaults with less restrictive throughput/tool posture
- `permissive`: minimal blocking posture for low-risk/internal experimentation
- `custom`: no profile defaults; user policy defines behavior

User overrides in `guardrails:` always take precedence over profile defaults.

## 3b) Per-user customization without code changes

Use `telemetry.custom_fields` to stamp tenant/team metadata on all events:

```yaml
telemetry:
  enabled: true
  custom_fields:
    team: "research"
    tenant: "acme"
    app: "agent-portal"
```

Use env overrides for deployment-specific changes:

- `GOV_GUARDRAILS__PROFILE=balanced`
- `GOV_TELEMETRY__LOG_LEVEL=DEBUG`

## 3c) Load custom guardrails policy (easy path)

Users can keep package defaults and swap policy only.

Create `guardrails.yaml` in app repo, then set:

```yaml
guardrails:
  profile: custom
  policy_file: "guardrails.yaml"
  model_schema_file: "model_schema.yaml"
```

No code changes are required when using `init_governance("governance.yaml")`.

Optional explicit override in code:

```python
from agent_governance.integrations import GovernanceADKMiddleware

gov = GovernanceADKMiddleware.from_config(
    "governance.yaml",
    guardrails_path="/absolute/path/to/guardrails.yaml",
)
```

## 3d) Agent metadata: required vs custom

Required core metadata in `agent`:

- `agent_id`
- `agent_name`
- `agent_type`
- `version`
- `env`
- `gcp_project`

For extra business metadata (team/owner/tenant/cost-center), use telemetry fields:

```yaml
telemetry:
  custom_fields:
    team: "research"
    owner: "platform-ai"
    tenant: "acme"
    cost_center: "RND-42"
```

These custom fields are emitted on all governance events.

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

Guardrails policy observability (current build):

- `agent_request_start` includes:
  - `attributes.guardrails_enabled`
  - `attributes.guardrails_policy`
  - `attributes.guardrails_policy_fingerprint`
- startup emits `safety_event` with `event=guardrails_policy_loaded`
- when guardrails are disabled, `error_event` is emitted with:
  - `attributes.alert_type=guardrails_disabled`
  - `attributes.severity=critical`

In GCP runtimes, Cloud Logging is auto-enabled when telemetry cloud settings are not explicitly configured.

Tracing note:

- if tracing is enabled and Cloud Trace export fails with `PermissionDenied`, grant runtime service account role `roles/cloudtrace.agent`.

## 9) Related docs

- [docs/CUSTOMER_QUICKSTART.md](CUSTOMER_QUICKSTART.md)
- [README.md](../README.md)
- [docs/ADK_USER_GUIDE.md](ADK_USER_GUIDE.md)
- [docs/ADK_E2E_GUIDE.md](ADK_E2E_GUIDE.md)
- [docs/REFERENCE_ARCHITECTURE.md](REFERENCE_ARCHITECTURE.md)