# Cloud Run + GitHub Actions Production Test Guide

This guide shows how to validate `adk-multiagent-test` in production-like Cloud Run, without changing SDK internals.

## Safe structure (recommended)

Keep boundaries strict:

- SDK code: `src/agent_governance/**` (treat as product code)
- deployment app code: `adk-multiagent-test/deploy/cloud_run/**`
- CI templates: `examples/github_actions/**`

Only deploy from `adk-multiagent-test/deploy/cloud_run` so you do not risk breaking SDK package behavior.

## Files added for Cloud Run test app

- service app: `adk-multiagent-test/deploy/cloud_run/main.py`
- service config: `adk-multiagent-test/deploy/cloud_run/governance.yaml`
- container build: `adk-multiagent-test/deploy/cloud_run/Dockerfile`
- workflow template: `examples/github_actions/cloudrun_adk_multiagent_prod_test.yaml`
- legacy-style workflow template: `examples/github_actions/cloudrun_adk_multiagent_legacy_credentials.yaml`

## If you already use `credentials_json` workflows

You can keep that pattern and still deploy this app safely.

Use:

- `examples/github_actions/cloudrun_adk_multiagent_legacy_credentials.yaml`

This mirrors your old flow:

- Docker buildx + push to Artifact Registry
- `deploy-cloudrun@v2` action
- service URL output + smoke test

## GitHub Actions setup

1. Copy template workflow to `.github/workflows/cloudrun_adk_multiagent_prod_test.yaml`.
2. Create GitHub variables:
   - `GCP_PROJECT_ID`
   - `GCP_REGION`
   - `AZURE_OPENAI_ENDPOINT`
   - `AZURE_OPENAI_API_VERSION`
   - `AZURE_OPENAI_DEPLOYMENT_NAME`
   - `AZURE_OPENAI_SCOPE`
   - `AZURE_OPENAI_TOKEN_URL`
3. Create GitHub secrets:
   - `GCP_WIF_PROVIDER`
   - `GCP_DEPLOYER_SA`
4. In GCP Secret Manager, create secrets:
   - `AZURE_OPENAI_CLIENT_ID`
   - `AZURE_OPENAI_CLIENT_SECRET`

If using legacy credentials style, also add GitHub secret:

- `GCP_CREDENTIALS` (service account JSON)

## Deployment gate (built-in in workflow templates)

Both Cloud Run workflow templates now run a deployment gate before build/deploy:

- `python scripts/validate_config.py adk-multiagent-test/deploy/cloud_run/governance.yaml --deployment-gate`

The gate fails the workflow if:

- required `agent` metadata is missing/empty (`agent_id`, `agent_name`, `agent_type`, `version`, `env`, `gcp_project`, `region`)
- `guardrails.enabled` is false
- no enforceable guardrails controls are present

For template configs where `agent.gcp_project` is set by environment, the workflows pass:

- `GOV_AGENT__GCP_PROJECT=${{ env.PROJECT_ID }}`
- `GOV_AGENT__REGION=${{ env.REGION }}`

## IAM roles for deployer service account

Grant minimal required roles:

- Cloud Run Admin
- Service Account User (on runtime SA)
- Artifact Registry Writer
- Cloud Build Editor
- Secret Manager Secret Accessor

## Production validation sequence

Workflow deploys image and then calls:

- `GET /health`
- `POST /smoke`

Expected result:

- `health.status = ok`
- `smoke.ok = true`
- governance events in Cloud Logging (`registration_event`, request events)

## Do not risk package stability

Use this rule:

- If changing runtime behavior for deployment only, change files under `adk-multiagent-test/deploy/**`.
- If changing SDK API or core governance behavior, change `src/agent_governance/**` and run full tests before deploy.

## Rollback plan

- Keep previous image tags.
- On failure, redeploy last good tag:
  - `gcloud run deploy <service> --image <previous-tag>`
