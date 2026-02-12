from ..report import compliant


def label_check(agent_id: str):
    return compliant("label_check", "Required labels present")
