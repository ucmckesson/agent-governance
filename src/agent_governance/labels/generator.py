from __future__ import annotations

from typing import Dict

from ..models import RegistryRecord


class LabelGenerator:
    def generate(self, record: RegistryRecord) -> Dict[str, str]:
        return {
            "agent_id": record.agent_id,
            "risk_tier": record.risk_tier.value,
            "data_classification": record.data_classification.value,
            "lifecycle": record.lifecycle.value,
        }
