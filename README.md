# agent-governance-sdk

SDK for implementing standard guardrails, data models for custom logging and evals for agents.

## Installation

- From GitHub (tagged release):
	- git+https://github.com/ucmckesson/agent-governance.git@v0.1.1
- Local development (from repo root):
	- pip install -e .

## Quick start

1) Create a governance.yaml at your repo root.

2) Initialize the SDK:

```python
from agent_governance import GuardrailsEngine, DLPScanner, init_telemetry, load_config

cfg = load_config("governance.yaml")
logger = init_telemetry(cfg.section("telemetry"))
guardrails = GuardrailsEngine(cfg.section("guardrails"))
dlp = DLPScanner()
```

## ADK integration

```python
from agent_governance.integrations import GovernanceADKMiddleware

governance = GovernanceADKMiddleware.from_config("governance.yaml")
```

## Guardrails policy & model schema

You can reference team-specific YAML files from governance.yaml:

- guardrails.policy_file
- guardrails.model_schema_file

## Guides

- See [docs/ADK_USER_GUIDE.md](docs/ADK_USER_GUIDE.md)
- See [docs/ADK_E2E_GUIDE.md](docs/ADK_E2E_GUIDE.md)
- See [docs/REFERENCE_ARCHITECTURE.md](docs/REFERENCE_ARCHITECTURE.md)

## Package layout

- `agent_governance.config` — configuration loader
- `agent_governance.telemetry` — structured logging
- `agent_governance.guardrails` — tool/input/output enforcement
- `agent_governance.dlp` — PII scanning
- `agent_governance.registry` — registry client
- `agent_governance.eval` — eval harness
- `agent_governance.compliance` — compliance checks
- `agent_governance.labels` — label validation
- `agent_governance.golden_data` — golden dataset utilities

## Examples

See [examples/](examples/) for ADK, Cloud Run, and GitHub Actions usage.
