from agent_governance.config import load_config


def test_load_config(fixtures_dir, monkeypatch):
    path = fixtures_dir / "sample_governance.yaml"
    cfg = load_config(path)
    assert cfg.agent.agent_id == "sample-agent"
