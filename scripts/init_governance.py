from __future__ import annotations

from pathlib import Path

TEMPLATE = """agent:
  agent_id: {agent_id}
  agent_name: {agent_name}
  agent_type: custom
  version: "0.1.0"
  env: dev
  gcp_project: {gcp_project}
telemetry:
  enabled: true
  redaction_keys: ["authorization", "secret", "token"]
  buffer_size: 100
"""


def main() -> None:
    agent_id = input("agent_id: ").strip()
    agent_name = input("agent_name: ").strip()
    gcp_project = input("gcp_project: ").strip()
    content = TEMPLATE.format(agent_id=agent_id, agent_name=agent_name, gcp_project=gcp_project)
    Path("governance.yaml").write_text(content)
    print("Created governance.yaml")


if __name__ == "__main__":
    main()
