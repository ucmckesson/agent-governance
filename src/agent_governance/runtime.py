from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class RuntimeMetadata:
    platform: str
    project_id: str | None = None
    region: str | None = None
    service_name: str | None = None
    revision: str | None = None
    service_url: str | None = None

    @property
    def is_gcp(self) -> bool:
        return self.platform in {"cloud_run", "gke", "agent_engine", "gcp"}


def detect_runtime() -> RuntimeMetadata:
    # Cloud Run
    if os.getenv("K_SERVICE"):
        return RuntimeMetadata(
            platform="cloud_run",
            project_id=os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT"),
            region=os.getenv("K_REGION") or os.getenv("GOOGLE_CLOUD_REGION"),
            service_name=os.getenv("K_SERVICE"),
            revision=os.getenv("K_REVISION"),
            service_url=os.getenv("CLOUD_RUN_URL") or os.getenv("SERVICE_URL"),
        )

    # Agent Engine / Vertex-style runtime hints
    if os.getenv("AIP_MODEL_DIR") or os.getenv("VERTEX_AI_AGENT_ENGINE"):
        return RuntimeMetadata(
            platform="agent_engine",
            project_id=os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT"),
            region=os.getenv("GOOGLE_CLOUD_REGION") or os.getenv("AIP_REGION"),
            service_name=os.getenv("AIP_ENDPOINT_ID") or os.getenv("AIP_MODEL_NAME"),
            revision=os.getenv("AIP_DEPLOYED_MODEL_ID"),
        )

    # GKE / generic GCP
    if os.getenv("KUBERNETES_SERVICE_HOST") and (
        os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
    ):
        return RuntimeMetadata(
            platform="gke",
            project_id=os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT"),
            region=os.getenv("GOOGLE_CLOUD_REGION"),
            service_name=os.getenv("HOSTNAME"),
        )

    return RuntimeMetadata(platform="local")
