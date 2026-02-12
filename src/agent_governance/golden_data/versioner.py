from __future__ import annotations

import hashlib
import json
from typing import Iterable, Dict


def dataset_hash(items: Iterable[Dict[str, object]]) -> str:
    normalized = json.dumps(list(items), sort_keys=True)
    return hashlib.sha256(normalized.encode()).hexdigest()[:12]
