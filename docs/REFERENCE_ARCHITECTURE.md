# Reference Architecture: Agent Governance SDK + ADK + Azure OpenAI + OTel

## 1) Purpose

This architecture shows how to deploy `agent-governance-sdk` as the governance and observability control plane around an ADK multi-agent runtime.

## 2) Logical components

- **Client/App Layer**
  - Sends user prompts to an ADK runner endpoint.
- **ADK Runtime Layer**
  - Orchestrator + specialist agents.
  - A2A routing via `transfer_to_agent` / sub-agents.
- **Governance Layer (this package)**
  - `GovernanceADKMiddleware`
  - `GuardrailsEngine`
  - `DLPScanner`
  - `GovernanceLogger`
- **Model Layer**
  - Azure OpenAI (deployment-specific model endpoint).
- **Telemetry Layer**
  - OpenTelemetry spans
  - Structured JSON governance events
  - Export targets: Cloud Logging / Cloud Trace / BigQuery (optional)

## 3) Request lifecycle

1. Request arrives at ADK runner.
2. `GovernanceADKMiddleware.before_agent_call()` executes:
   - Create `RequestContext`
   - Emit `agent_request_start`
   - Run input guardrails
   - Run input DLP action (log/redact/block)
3. ADK executes agent graph:
   - Orchestrator LLM decision
   - Optional A2A delegation to specialist(s)
   - Optional tool execution
   - Additional model calls
4. `GovernanceADKMiddleware.after_agent_call()` executes:
   - Run output guardrails
   - Run output DLP action
   - Emit `agent_request_end`
5. OTel spans and governance events are exported.

## 4) Control points

- **Before agent**: topic, injection, rate, schema checks.
- **Before tool**: allow/deny, param/schema checks, confirmation, circuit breaker.
- **After tool**: result status recorded.
- **After agent**: output safety/schema and DLP.

## 5) Observability contract

### OTel spans (examples)
- `invocation`
- `invoke_agent <agent_name>`
- `call_llm`
- `execute_tool <tool_name>`
- `a2a_delegation`
- `guardrail.<rule_name>`

### Governance events (JSON)
- `agent_request_start`
- `agent_request_end`
- `tool_call_start`
- `tool_call_end`
- `safety_event`
- `error_event`

Recommended correlation keys:
- `request_id`
- `trace_id`
- `span_id`
- `session_id`
- `agent_id`

## 6) Deployment topology (recommended)

- Containerized ADK service on Cloud Run / GKE.
- Package config via `governance.yaml` + environment overrides.
- OTel exporter to Cloud Trace (or OTLP collector).
- Structured governance logs to Cloud Logging.
- Optional sink from Cloud Logging to BigQuery for audit analytics.

## 7) Minimal integration pattern

- Build ADK runner/agent tree.
- Initialize `GovernanceADKMiddleware.from_config()`.
- Wrap each user request with:
  - `before_agent_call()`
  - ADK run
  - `after_agent_call()`

This keeps business-agent code separate from policy and telemetry concerns.

## 8) Non-functional guarantees

- Fail-closed guardrails on internal guardrail errors.
- Config-driven policy without app code changes.
- Deterministic telemetry envelope for operations and compliance.

## 9) Production bootstrap model

Use `init_governance()` to initialize the full runtime in one call:

- config load + env overrides
- runtime detection (`cloud_run`, `agent_engine`, `gke`, `local`)
- telemetry setup (auto Cloud Logging on GCP when enabled by runtime)
- ADK middleware wiring
- startup registration event + periodic heartbeat

For FastAPI on Cloud Run, use `cloud_run_fastapi_runtime(app, config_path)` to:

- add telemetry middleware
- register startup lifecycle
- attach shutdown handlers (`mark_stopped`, `stop_heartbeat`)

This is the recommended pattern for pip-installed adopters who want agent
activity automatically logged in Cloud Logging after deployment.
