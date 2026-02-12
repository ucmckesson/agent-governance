from __future__ import annotations

import sys

from agent_governance.config import load_config


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "governance.yaml"
    load_config(path)
    print("Config valid")


if __name__ == "__main__":
    main()
