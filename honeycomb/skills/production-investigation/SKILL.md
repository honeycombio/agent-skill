---
name: Honeycomb Production Investigation
description: >
  This skill should be used when the user asks to "investigate a production issue",
  "debug a latency spike", "find root cause", "use BubbleUp", "analyze traces",
  "explore a trace waterfall", "investigate an alert", "find what changed",
  "compare outliers", "debug an outage", "investigate slow requests",
  "analyze an incident", "look at trace details", "find anomalies",
  "why is my API slow", "why are requests failing", "what's causing errors",
  "investigate a service", "check service dependencies", "view service map",
  or needs a structured workflow for debugging production problems using Honeycomb.
  For help constructing complex queries, see the query-patterns skill.
version: 1.0.0
---

# Honeycomb Production Investigation

Structured workflows for debugging production issues using the Honeycomb MCP server.
Combines context discovery, trace exploration, BubbleUp outlier analysis, service map,
and systematic investigation to find root causes.

## MCP Tools for Investigation

**Context Discovery:**
- **`get_workspace_context`** — Starting point: team info, environments, datasets
- **`get_environment`** — Environment details and dataset list
- **`find_columns`** — Discover available fields by intent
- **`get_dataset_columns`** — List columns with sample values
- **`find_queries`** — Search past queries for relevant prior investigations

**Query & Analysis:**
- **`run_query`** — Run targeted queries to characterize issues
- **`run_bubbleup`** — Compare outliers against baseline to identify differentiators
- **`get_query_results`** — Retrieve results from a prior query run

**Trace & Dependency Analysis:**
- **`get_trace`** — Fetch complete trace for span-level analysis
- **`get_service_map`** — Visualize service dependencies and traffic flow

**Reliability Context:**
- **`get_slos`** — Check SLO compliance, budget, and burn rate
- **`get_triggers`** — Check trigger status and alert history

**Documentation:**
- **`create_board`** — Record investigation findings as a Board
- **`list_boards`** — Find existing relevant Boards

## Investigation Workflow

### Step 1: Prime Context
Before investigating, discover available data:
1. Call `get_workspace_context` for team, environments, and datasets
2. Call `find_columns` for the target environment/dataset
3. Call `find_queries` to check for prior relevant investigations
4. If SLO-related: call `get_slos` to see current compliance and burn rate
5. If alert-related: call `get_triggers` to see trigger details and status

### Step 2: Identify the Problem
Run broad queries to characterize the issue:
- **Latency spikes**: `VISUALIZE P99(duration_ms), HEATMAP(duration_ms) WHERE is_root GROUP BY name`
- **Error surges**: `VISUALIZE COUNT WHERE error = true GROUP BY service.name, name`
- **Traffic changes**: `VISUALIZE COUNT WHERE is_root GROUP BY http.route`
- **Service dependencies**: Call `get_service_map` to understand traffic flow and P95 durations

### Step 3: Use BubbleUp to Find Differentiators
Once a problem is visible in query results:
1. Run the query that shows the anomaly via `run_query`
2. Call `run_bubbleup` on the query result, specifying the outlier region
3. BubbleUp compares the outlier selection against the baseline
4. Look for fields where the outlier distribution differs significantly from baseline

**BubbleUp selection types:**
- **2D heatmap selection**: Specify `time_start`, `time_end`, `min_value`, `max_value`, and `column`
- **Group selection**: Specify a `group` map of column names to exact values
- **Time-based selections** support flexible formats: percentages (`"80%"`), time labels (`"01:48"`), relative offsets (`"-5m"`), keywords (`"start"`, `"middle"`, `"end"`)

**What BubbleUp reveals:**
- Dimensions (categorical): Which values are overrepresented in outliers
- Measures (numeric): How numeric distributions shift in outliers
- Typical findings: deployment version, user cohort, region, endpoint

### Step 4: Drill Into Traces
After BubbleUp identifies suspects:
1. Add BubbleUp findings as WHERE filters to narrow the query
2. Pick a representative trace ID from results
3. Call `get_trace` to fetch the full trace
4. Examine the waterfall for: slow spans, errors, gaps, unexpected fan-out

**`get_trace` view modes:**
- `auto` (default): Smart collapsing for readability
- `compact`: Aggressive collapsing for large traces
- `full`: Show everything including span events
- `focused`: Focus on a specific span and its descendants (requires `focus_span_id`)

**What to look for in traces:**
- Spans with disproportionately long duration vs parent
- Sequential spans that could be parallelized (N+1 patterns)
- Error spans and their span events (stack traces, messages)
- Service boundaries (where traces cross services)
- Gaps between child spans (missing instrumentation or idle time)

### Step 5: Formulate and Verify Hypothesis
Based on BubbleUp + trace analysis:
1. Form a hypothesis (e.g., "deployment v2.3.1 introduced a slow DB query for /checkout")
2. Verify by querying: `VISUALIZE P99(duration_ms) WHERE deployment.version = "v2.3.1" GROUP BY name`
3. Compare against baseline: Same query with `WHERE deployment.version != "v2.3.1"`

### Step 6: Record Findings
Call `create_board` to document the investigation with:
- Summary text panel (Markdown)
- Key queries that identified the problem (pass query run PKs)
- Related SLOs if applicable

## Common Investigation Patterns

### Latency Spike
1. `HEATMAP(duration_ms) WHERE is_root` — See the distribution shift
2. `run_bubbleup` on the slow region — Find what's different
3. `get_trace` on a slow trace — See where time is spent
4. Narrow with WHERE filters from BubbleUp findings

### Error Surge
1. `COUNT WHERE error = true GROUP BY exception.message` — Categorize errors
2. `run_bubbleup` on the error spike — Find correlated attributes
3. `get_trace` on an errored trace — See the error in context

### Deployment Regression
1. `P99(duration_ms) WHERE is_root GROUP BY deployment.version` — Compare versions
2. `run_bubbleup` comparing new vs old version traffic
3. `get_trace` on slow traces from the new version

### Dependency Failure
1. `get_service_map` — Visualize service dependencies
2. `P99(duration_ms) WHERE service.name = "[dependency]" GROUP BY name` — Check dependency health
3. `COUNT WHERE any.service.name = "[dependency]" AND any.error = true GROUP BY root.name` — Impact assessment
4. `get_trace` on an affected trace — Find timeouts, errors, retries

## Troubleshooting Empty/Unexpected Results

- **No results**: Check field names with `find_columns`, expand time range, verify environment/dataset
- **BubbleUp shows no clear signal**: Try different time range, add more specific filters, check that selection clearly separates from baseline
- **Trace is missing spans**: May indicate sampling, instrumentation gaps, or cross-environment trace split
- **MCP session expired**: Re-authenticate (OAuth) or check API key

## Additional Resources

### Reference Files
- **`references/trace-exploration.md`** — Detailed trace waterfall navigation and span analysis
- **`references/bubbleup-guide.md`** — Complete BubbleUp usage guide with selection types and interpretation
- **`references/investigation-playbooks.md`** — Step-by-step playbooks for common incident types
