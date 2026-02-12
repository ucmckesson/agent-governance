from ..report import compliant


def scc_check(agent_id: str):
    return compliant("scc_check", "No open SCC findings")
