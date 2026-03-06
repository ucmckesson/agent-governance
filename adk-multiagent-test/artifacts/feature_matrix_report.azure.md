# Governance Feature Matrix Report

- Mode: **azure_openai**
- Passed: **19/19**

## Checks

| Feature | Status | Details |
|---|---|---|
| agent_request_start emitted | PASS | ['agent_request_start', 'agent_request_end', 'metric_event', 'agent_delegation', 'cost_event', 'agent_request_start', 'agent_request_end', 'metric_event', 'agent_delegation', 'cost_event', 'agent_requ |
| agent_request_end emitted | PASS | ['agent_request_start', 'agent_request_end', 'metric_event', 'agent_delegation', 'cost_event', 'agent_request_start', 'agent_request_end', 'metric_event', 'agent_delegation', 'cost_event', 'agent_requ |
| dlp_event emitted | PASS | ['agent_request_start', 'agent_request_end', 'metric_event', 'agent_delegation', 'cost_event', 'agent_request_start', 'agent_request_end', 'metric_event', 'agent_delegation', 'cost_event', 'agent_requ |
| cost_event emitted | PASS | ['agent_request_start', 'agent_request_end', 'metric_event', 'agent_delegation', 'cost_event', 'agent_request_start', 'agent_request_end', 'metric_event', 'agent_delegation', 'cost_event', 'agent_requ |
| agent_delegation emitted | PASS | ['agent_request_start', 'agent_request_end', 'metric_event', 'agent_delegation', 'cost_event', 'agent_request_start', 'agent_request_end', 'metric_event', 'agent_delegation', 'cost_event', 'agent_requ |
| metric_event emitted | PASS | ['agent_request_start', 'agent_request_end', 'metric_event', 'agent_delegation', 'cost_event', 'agent_request_start', 'agent_request_end', 'metric_event', 'agent_delegation', 'cost_event', 'agent_requ |
| prompt fingerprint attributes present | PASS | start_events=4 |
| dlp info types populated | PASS | dlp_events=1 |
| session span attributes present | PASS | span_count=59 |
| delegation span present | PASS | search span name agent_delegation |
| cost span present | PASS | search span name llm_cost |
| cloud logging trace/span fields present | PASS | entries=59 |
| runtime metrics snapshot generated | PASS | {"requests_total": 4, "errors_total": 0, "error_rate": 0.0, "request_p95_latency_ms": 14131, "delegations_total": 3, "cost_usd_total": 0.0, "input_tokens_total": 6824, "output_tokens_total": 3366, "to |
| delegation edges tracked | PASS | [{'source_agent': 'orchestrator', 'target_agent': 'research_agent', 'count': 2}, {'source_agent': 'orchestrator', 'target_agent': 'validator_agent', 'count': 1}] |
| dlp model_armor provider selectable | PASS | model_armor |
| dlp provider differentiation | PASS | sdp=6 model_armor=4 |
| annotation export works | PASS | items=3 |
| trace capture by session works | PASS | items=1 |
| experiment comparison computes deltas | PASS | {"task_completion": 0.1} |

## Scenario Outputs

| Session | Query | Transfers | Output (trimmed) |
|---|---|---|---|
| session-clean | What is the capital of France? | research_agent | Paris. |
| session-validate | Validate this value: sample_data | validator_agent | {"valid": true, "reasons": []} |
| session-pii | My email is alice@example.com and my SSN is 123-45-6789 | none | Request blocked: email detected. Please remove personal information. |
| session-topic | Tell me about banned_topic | research_agent | I’m not sure what you mean by “banned_topic.” If you’re referring to content that’s prohibited because it enables harm o |