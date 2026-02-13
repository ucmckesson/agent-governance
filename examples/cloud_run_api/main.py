from fastapi import FastAPI

from agent_governance.integrations import cloud_run_fastapi_runtime

app = FastAPI()
runtime = cloud_run_fastapi_runtime(app, config_path="governance.yaml")


@app.get("/")
def health():
    return {
        "status": "ok",
        "agent_id": runtime.config.agent.agent_id,
        "runtime": runtime.runtime.platform,
    }
