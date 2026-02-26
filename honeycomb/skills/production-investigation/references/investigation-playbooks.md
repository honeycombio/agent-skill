# Investigation Playbooks

Step-by-step playbooks for common production incident types. Each playbook uses
Honeycomb MCP tools in a structured sequence.

## Playbook: Latency Spike

**Trigger**: Alert fires for elevated P99 latency or user reports slowness.

1. **Prime context**: `get_workspace_context` -> `find_columns` for target dataset
2. **Characterize**: `run_query` with `HEATMAP(duration_ms), P99(duration_ms) WHERE is_root GROUP BY name`
   - Is it affecting all endpoints or specific ones?
   - Is it a gradual increase or sudden jump?
3. **BubbleUp on the slow region**: `run_bubbleup` on the heatmap outlier area
   - Look for: deployment version, region, specific endpoint, database query
4. **Trace analysis**: `get_trace` on a slow trace from the affected population
   - Where does the time go? Which span is disproportionately slow?
   - Is it a single slow dependency or cumulative slowness?
5. **Compare**: Query the suspected cause
   - `P99(duration_ms) WHERE [bubbleup finding] GROUP BY name`
   - Confirm by negation: `WHERE NOT [bubbleup finding]`
6. **Record**: `create_board` with key queries and findings

**Expected outcome**: Identified which deployment, service, or endpoint is responsible for the latency increase. A healthy trace waterfall shows spans nested tightly with minimal gaps; large gaps may indicate missing instrumentation.

## Playbook: Error Surge

**Trigger**: Error rate alert, increased exception volume, or user error reports.

1. **Prime context**: `get_workspace_context` -> `find_columns`
2. **Categorize errors**: `run_query` with `COUNT WHERE error = true GROUP BY exception.message`
   - Is it one error type or many?
   - Are errors new or pre-existing but increased?
3. **Find affected scope**: `COUNT WHERE error = true GROUP BY service.name, http.route`
   - Which services and endpoints are affected?
4. **BubbleUp on error traffic**: `run_bubbleup` comparing errored vs successful traffic
   - Look for: request parameters, user attributes, deployment version
5. **Trace an error**: `get_trace` on an errored trace with `show_events: true`
   - Where does the error originate?
   - Is it a dependency failure (deep span) or application error (shallow span)?
   - Check span events for stack traces
6. **Verify fix scope**: Query to confirm the error pattern
   - `COUNT WHERE [error condition] GROUP BY [suspected cause]`

## Playbook: Deployment Regression

**Trigger**: Issues observed after a deployment.

1. **Prime context**: `find_columns` — look for deployment-related fields
2. **Compare versions**: `P99(duration_ms), COUNT WHERE is_root GROUP BY deployment.version`
   - Does the new version show different latency or error patterns?
3. **BubbleUp comparing versions**: `run_bubbleup` with group selection on new version
   - What's different about the new version's behavior?
4. **Narrow to affected operations**: Add WHERE filters from BubbleUp
   - Which specific operations are affected?
5. **Trace comparison**: `get_trace` on traces from both versions
   - What changed in the span structure or timing?

## Playbook: Dependency Failure

**Trigger**: Downstream service or database issues suspected.

1. **Check architecture**: `get_service_map` to understand service dependencies
2. **Check dependency health**: `P99(duration_ms), COUNT WHERE service.name = "[dependency]" GROUP BY name`
   - Is the dependency slower or erroring more?
3. **Impact assessment**: `COUNT WHERE any.service.name = "[dependency]" AND any.error = true GROUP BY root.name`
   - Which upstream services and endpoints are affected?
4. **Trace through the dependency**: `get_trace` on an affected trace
   - Is it timeout, error, or slow response?
   - Are retries visible (repeated child spans)?
5. **Isolate**: Confirm dependency is the cause
   - `P99(duration_ms) WHERE child.service.name = "[dependency]" GROUP BY name`

## Playbook: SLO Budget Burn

**Trigger**: SLO burn alert fires or budget consumption rate increasing.

1. **Check SLO status**: `get_slos` with the SLO ID for detailed compliance, budget, and burn rate
2. **Identify timing**: When did the burn rate increase? Use the budget burndown graph.
3. **Find contributing failures**: Run the SLI query with error groupings
   - If latency SLO: `COUNT WHERE duration_ms > [SLI threshold] GROUP BY name, service.name`
   - If availability SLO: `COUNT WHERE http.status_code >= 500 GROUP BY name, service.name`
4. **BubbleUp on failures**: `run_bubbleup` to find what differentiates failing events
5. **Trace failing events**: `get_trace` on representative failures
6. **Quantify impact**: How much budget was consumed and by what?

## Playbook: General Health Check

**Trigger**: User wants a broad overview of production health.

1. **Prime context**: `get_workspace_context` -> `get_environment`
2. **Check SLOs**: `get_slos` — any SLOs triggered or budgets low?
3. **Check triggers**: `get_triggers` — any active alerts?
4. **Architecture overview**: `get_service_map` — any unusual traffic patterns?
5. **Error scan**: `COUNT WHERE error = true GROUP BY service.name` (last 2 hours)
6. **Latency scan**: `P99(duration_ms) WHERE is_root GROUP BY name` (last 2 hours)
7. **Traffic scan**: `COUNT WHERE is_root GROUP BY http.route` (last 2 hours vs last 24 hours)
8. **Report**: Summarize findings, flag any anomalies
