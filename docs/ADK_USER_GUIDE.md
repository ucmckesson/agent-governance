### guardrails example (default)

```yaml
# Strict Agent Guardrails Configuration
# Focus: Security, PII, Harmful Content, Hallucination, and Action Control

name: strict-production-guardrails
version: "2026-02-11"

# --- INPUT GUARDRAILS (Before prompt hits the LLM) ---
input_guardrails:
  # 1. Detect prompt injections and jailbreaks
  - type: prompt_injection
    threshold: 0.8
    action: block
  
  # 2. Prevent PII leakage in user inputs (email, SSN, credit cards)
  - type: pii_redaction
    entities: ["EMAIL_ADDRESS", "CREDIT_CARD", "SSN", "PHONE_NUMBER"]
    action: redact
    
  # 3. Topic/Keyword filtering (Strict deny-list)
  - type: topic_filter
    disallowed_topics:
      - illegal_acts
      - sexual_content
      - competitor_data
      - PII_extraction
    action: block

# --- OUTPUT GUARDRAILS (After LLM response, before user sees it) ---
output_guardrails:
  # 1. Hallucination detection
  - type: grounding_check
    threshold: 0.95 # Require high confidence
    action: block
    
  # 2. Content moderation (Hate speech, bias, violence)
  - type: content_safety
    severity: high
    action: block
    
  # 3. Final PII check
  - type: pii_redaction
    entities: ["EMAIL_ADDRESS", "CREDIT_CARD", "SSN"]
    action: redact

# --- TOOL/ACTION GUARDRAILS (Before agent executes commands) ---
action_guardrails:
  # 1. Least-privilege access for tools
  - type: tool_authorization
    allowed_tools: ["search_internal_kb", "read_read_only_db"]
    disallowed_tools: ["execute_shell", "delete_file", "write_to_prod_db"]
    action: restrict
    
  # 2. Human-in-the-loop (HITL) for high-impact actions
  - type: approval_gate
    actions: ["email_user", "update_customer_record"]
    action: require_approval

# --- MONITORING & LOGGING ---
logging:
  enabled: true
  log_level: DEBUG # Log all input/output for audit trails
  
# --- RATE LIMITING ---
rate_limits:
  max_requests_per_minute: 10
  max_tokens_per_minute: 5000
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

## 3b) Telemetry to Cloud Logging

Add this to governance.yaml to send logs to Google Cloud Logging:

```yaml
telemetry:
  enabled: true
  log_level: "INFO"
  redact_fields: ["token", "authorization", "secret"]
  cloud_logging:
    enabled: true
    project: "my-gcp-project"
    log_name: "agent-governance"
    labels:
      service: "my-agent"
    also_stdout: true
```

## 4) Wire into ADK

```python
from agent_governance.integrations import GovernanceADKMiddleware

# Create middleware from governance.yaml
governance = GovernanceADKMiddleware.from_config("governance.yaml")

# Optional: override guardrails policy file
# governance = GovernanceADKMiddleware.from_config(
#   "governance.yaml",
#   guardrails_path="/path/to/custom-guardrails.yaml",
# )

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
```

## Notes

- Telemetry fails open. Guardrails fail closed.
- This strict guardrails policy is the SDK default when guardrails are omitted.
- If you need team-specific policies, update guardrails.yaml and model_schema.yaml only.
