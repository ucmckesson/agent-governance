from __future__ import annotations

import argparse
import sys
from typing import Any

from agent_governance.config import load_config


def _is_non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _run_deployment_gate(path: str) -> None:
    cfg = load_config(path)
    errors: list[str] = []

    agent = cfg.agent
    required_agent_fields = [
        "agent_id",
        "agent_name",
        "agent_type",
        "version",
        "env",
        "gcp_project",
        "region",
    ]
    for field in required_agent_fields:
        value = getattr(agent, field, None)
        if value is None:
            errors.append(f"agent.{field} is missing")
            continue
        if isinstance(value, str) and not _is_non_empty(value):
            errors.append(f"agent.{field} must be non-empty")

    guardrails = cfg.section("guardrails")
    if not isinstance(guardrails, dict) or not guardrails:
        errors.append("guardrails section is missing")
    else:
        if not bool(guardrails.get("enabled", True)):
            errors.append("guardrails.enabled must be true for GCP deployment")

        has_controls = any(
            [
                bool(guardrails.get("input_guardrails")),
                bool(guardrails.get("output_guardrails")),
                bool(guardrails.get("action_guardrails")),
                bool((guardrails.get("input_validation") or {}).get("block_known_injection_patterns")),
                bool((guardrails.get("content_safety") or {}).get("enabled", False)),
                bool((guardrails.get("tools") or {}).get("policies")),
                bool((guardrails.get("rate_limiting") or {}).get("enabled", False)),
            ]
        )
        if not has_controls:
            errors.append("guardrails has no enforceable controls")

    if errors:
        print("Deployment gate failed:\n")
        for err in errors:
            print(f"- {err}")
        sys.exit(1)

    print("Deployment gate passed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate governance config")
    parser.add_argument("path", nargs="?", default="governance.yaml")
    parser.add_argument(
        "--deployment-gate",
        action="store_true",
        help="Fail if required agent metadata or guardrails controls are missing for deployment",
    )
    args = parser.parse_args()

    if args.deployment_gate:
        _run_deployment_gate(args.path)
        return

    load_config(args.path)
    print("Config valid")


if __name__ == "__main__":
    main()
