from __future__ import annotations

from typing import Any, Dict, Optional


def enable_cloud_logging(logger, config: Dict[str, Any]) -> None:
    """Attach Google Cloud Logging handler if dependency is available."""
    try:
        from google.cloud import logging as cloud_logging  # type: ignore
    except Exception:
        return

    project = config.get("project")
    log_name = config.get("log_name", "agent_governance")
    labels = config.get("labels") or {}

    client = cloud_logging.Client(project=project) if project else cloud_logging.Client()
    handler = client.get_default_handler()
    handler.name = log_name

    if labels:
        try:
            handler.labels = labels
        except Exception:
            pass

    logger.addHandler(handler)

    if not config.get("also_stdout", True):
        logger.propagate = False
