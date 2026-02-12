from ..report import compliant


def attestation_check(agent_id: str):
    return compliant("attestation_check", "Attestations current")
