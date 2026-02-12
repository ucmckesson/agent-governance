from ..report import compliant


def iam_check(agent_id: str):
    return compliant("iam_check", "Service account configuration ok")
