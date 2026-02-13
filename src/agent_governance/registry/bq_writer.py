from __future__ import annotations

from typing import Any, Dict, Iterable, List

from ..exceptions import RegistryError
from .models import AgentRegistrationRecord


def write_registration(
    record: AgentRegistrationRecord,
    project: str,
    dataset: str,
    table: str,
) -> None:
    """Insert a registration record into BigQuery."""
    try:
        from google.cloud import bigquery  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RegistryError("google-cloud-bigquery not installed") from exc

    client = bigquery.Client(project=project)
    table_ref = f"{project}.{dataset}.{table}"
    row = record.model_dump(mode="json")
    errors = client.insert_rows_json(table_ref, [row])
    if errors:
        raise RegistryError(f"BigQuery insert errors: {errors}")
