from agent_governance.integrations import GovernanceADKMiddleware


async def main():
    governance = GovernanceADKMiddleware.from_config("governance.yaml")
    agent_identity = governance.agent

    user_input, ctx, start_time = await governance.before_agent_call(
        agent_identity, "hello", user_id="user-1", session_id="session-1"
    )

    # Simulate tool call
    tool_params = await governance.before_tool_call(agent_identity, ctx, "search", {"query": "hello"})
    tool_result = {"results": ["ok"]}
    await governance.after_tool_call(agent_identity, ctx, "search", tool_result, latency_ms=10, success=True)

    output = await governance.after_agent_call(agent_identity, ctx, user_input, start_time)
    print(output)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
