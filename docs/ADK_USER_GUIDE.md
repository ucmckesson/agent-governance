# ADK User Guide

This guide shows how to integrate the SDK while building agents with Google ADK. It focuses on end-to-end telemetry and guardrails, with team-customizable YAML files.

## 1) Add governance.yaml

Create a governance.yaml at your agent repo root. Point guardrails and model schema to team-owned YAML files.

```yaml
agent:
  agent_id: "customer-service-v2"
  agent_name: "Customer Service Agent v2"
  agent_type: "adk"
  version: "0.1.0"
  env: "dev"
  gcp_project: "my-project"

telemetry:
  enabled: true
  log_level: "INFO"
  redact_fields: ["token", "authorization", "secret"]
  custom_fields:
    team: "cx"
    product: "support"

guardrails:
  policy_file: "guardrails.yaml"
  model_schema_file: "model_schema.yaml"

dlp:
  enabled: true
  scan_input: true
  scan_output: true
  action_on_input_pii: "redact"
  action_on_output_pii: "redact"
```

## 2) Add guardrails.yaml

Each team can customize this file without changing code.

```yaml
enabled: true
tools:
  default_policy:
    allowed: false
  policies:
    - tool_name: "crm_search"
      allowed: true
      max_calls_per_request: 3
    - tool_name: "send_email"
      allowed: true
      requires_confirmation: true
input_validation:
  max_input_length: 10000
  max_input_tokens: 4096
  block_known_injection_patterns: true
output_validation:
  max_output_length: 50000
rate_limiting:
  enabled: true
  requests_per_minute_per_user: 30
  requests_per_minute_global: 500
content_safety:
  enabled: true
  block_categories: ["violence", "hate_speech"]
```

## 3) Add model_schema.yaml

Define input/output and tool parameter schemas.

```yaml
input_schema:
  type: object
  properties:
    text:
      type: string
  required: ["text"]

output_schema:
  type: object
  properties:
    text:
      type: string
  required: ["text"]

tool_params:
  crm_search:
    schema:
      type: object
      properties:
        query:
          type: string
      required: ["query"]
```

## 4) Wire into ADK

```python
from agent_governance.integrations import GovernanceADKMiddleware

# Create middleware from governance.yaml
governance = GovernanceADKMiddleware.from_config("governance.yaml")

# Example usage inside an ADK agent loop
async def handle_request(user_input: str, user_id: str):
  processed_input, ctx, start_time = await governance.before_agent_call(
    governance.agent, user_input, user_id=user_id
  )

  # Call your ADK agent here using processed_input
  output = "..."

  final_output = await governance.after_agent_call(
    governance.agent, ctx, output, start_time
  )
  return final_output
```

## 5) Tool calls

For tools, call the middleware before and after the tool execution:

```python
tool_params = await governance.before_tool_call(
  governance.agent, ctx, "crm_search", {"query": "status"}
)

# run tool with tool_params
result = {"status": "ok"}

await governance.after_tool_call(
  governance.agent, ctx, "crm_search", result, latency_ms=12, success=True
)
+```

## Notes

- Telemetry fails open. Guardrails fail closed.
- If you need team-specific policies, update guardrails.yaml and model_schema.yaml only.
