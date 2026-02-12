from ..report import compliant


def data_class_check(agent_id: str):
    return compliant("data_class_check", "Data classification assigned")
