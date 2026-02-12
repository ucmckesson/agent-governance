from __future__ import annotations

import os


def github_actions_env() -> dict:
    """Return environment variables commonly used in GitHub Actions."""
    return {
        "GITHUB_SHA": os.getenv("GITHUB_SHA"),
        "GITHUB_REF": os.getenv("GITHUB_REF"),
        "GITHUB_RUN_ID": os.getenv("GITHUB_RUN_ID"),
        "GITHUB_ACTOR": os.getenv("GITHUB_ACTOR"),
    }
