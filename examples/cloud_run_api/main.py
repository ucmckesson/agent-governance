from fastapi import FastAPI

from agent_governance import init_telemetry, load_config
from agent_governance.integrations import fastapi_middleware

cfg = load_config("governance.yaml")
logger = init_telemetry(cfg.section("telemetry"))

app = FastAPI()
fastapi_middleware(app, logger, cfg.agent)


@app.get("/")
def health():
    return {"status": "ok"}
