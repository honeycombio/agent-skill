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

Structured workflows for debugging production issues. The MCP tools document their
own parameters — this skill focuses on the *sequence* of tool calls and how to
*interpret* results to reach a root cause.

## Investigation Workflow

### Step 1: Orient
1. `get_workspace_context` → environments and datasets
2. `get_slos` → any SLOs in violation? (frames severity)
3. `get_triggers` → any alerts firing? (narrows scope)
4. `find_queries` → has anyone investigated this before?

### Step 2: Characterize the Problem
Run a broad query to see the shape of the issue:
- **Latency spike**: P99(duration_ms), HEATMAP(duration_ms) grouped by service or route
- **Error surge**: COUNT filtered on error=true, grouped by exception.message or service
- **Unknown**: COUNT grouped by service.name to find which service has anomalous volume

Also call `get_service_map` — it shows P95 durations between services and can immediately reveal which dependency is slow.

### Step 3: BubbleUp to Find Differentiators
This is the highest-value step. Once you have a query showing the anomaly:
1. Run `run_bubbleup` on the query result, selecting the outlier region
2. BubbleUp compares outlier vs baseline distributions across *all* columns automatically
3. Look for fields where the distributions differ significantly

**How to interpret BubbleUp results:**
- **Categorical fields** (dimensions): A value overrepresented in outliers points to a cause (e.g., `deployment.version=v2.3.1` is 90% of slow requests but only 20% of baseline)
- **Numeric fields** (measures): A shifted distribution shows correlated metrics (e.g., `db.query_duration` is much higher in outliers)
- **Typical root causes surfaced**: deployment version, region, user cohort, specific endpoint, feature flag

### Step 4: Drill Into Traces
After BubbleUp identifies suspects:
1. Add BubbleUp findings as WHERE filters to narrow results
2. Pick a representative trace ID
3. Call `get_trace` to fetch the full trace

**What to look for in the trace waterfall:**
- Spans with disproportionate duration vs parent (the bottleneck)
- Sequential spans that could be parallelized (N+1 query patterns)
- Error spans — check span events for stack traces
- Gaps between child spans (missing instrumentation or idle wait)
- Service boundaries (where the trace crosses services)

### Step 5: Verify Hypothesis
Form a hypothesis from BubbleUp + trace analysis, then confirm:
- Query WITH the suspected cause filtered in
- Query WITHOUT it (as a control)
- If the metrics diverge, you've found it

### Step 6: Record Findings
Call `create_board` with:
- A text panel summarizing the root cause (Markdown)
- The key query run PKs that identified the problem
- Related SLOs if applicable

## Investigation Patterns

### Latency Spike
HEATMAP first → BubbleUp the slow region → trace a slow request → verify with filtered queries

### Error Surge
COUNT errors grouped by exception.message → BubbleUp the error spike → trace an errored request → verify

### Deployment Regression
P99 grouped by deployment.version → BubbleUp comparing new vs old → trace from new version → verify

### Dependency Failure
`get_service_map` → P99 on the slow dependency → relational query (`any.service.name`) to measure user impact → trace an affected request

## When Results Are Empty or Unclear

- **No results**: Check field names with `find_columns`, expand time range, verify environment/dataset
- **BubbleUp shows no signal**: Try a different time selection, add filters to isolate the anomaly more clearly, or select a different calculation
- **Trace missing spans**: Sampling, instrumentation gaps, or cross-environment trace split
