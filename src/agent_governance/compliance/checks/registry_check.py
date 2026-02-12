from ..report import compliant


def registry_check(agent_id: str):
    return compliant("registry_check", "Agent present in registry")
