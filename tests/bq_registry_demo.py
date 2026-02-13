"""Insert a sample agent registration record into BigQuery."""

from datetime import datetime, timezone

from agent_governance.registry import AgentRegistrationRecord, write_registration


def main() -> None:
    record = AgentRegistrationRecord(
        agent_id="demo-agent",
        env="dev",
        runtime="cloud_run",
        service_name="demo-service",
        region="us-central1",
        cloud_run_url="https://demo-service-xyz.run.app",
        revision="demo-rev-001",
        version="0.1.1",
        owner="team@example.com",
        tools=["search"],
        datasources=["bq:dataset.table"],
        write_tools=["ticket_create"],
        last_deploy_times=[datetime.now(timezone.utc)],
        status="active",
    )

    write_registration(
        record,
        project="your-project-id",
        dataset="agent_registry",
        table="agent_registration",
    )


if __name__ == "__main__":
    main()
