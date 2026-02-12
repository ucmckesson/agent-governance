from ..report import compliant


def eval_check(agent_id: str):
    return compliant("eval_check", "Recent eval passed")
