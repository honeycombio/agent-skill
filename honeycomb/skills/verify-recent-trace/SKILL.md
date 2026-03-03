---
name: verify-recent-trace
description: >
  Find a recent trace in Honeycomb, to see what happened in a recent test. Use when asked to "verify in Honeycomb", "find the most recent trace", or "show me the trace".
metadata:
  version: "1.0.0"
allowed-tools:
  - mcp__honeycomb__run_query
  - mcp__honeycomb__get_trace
  - mcp__honeycomb__get_query_results
  - mcp__honeycomb__find_queries
  - Read
---

# Honeycomb Verification Skill

## Purpose

Query Honeycomb to find the traces that were created by a recent test.

## When to Use

This skill is automatically activated when:

- User asks to "show me a trace in Honeycomb"
- Completing an implementation step that requires observability verification

## Verification Output

Report query results as:
Queried [VIZ] where [FILTERS] by [GROUP_BY] over [TIME_RANGE]
Results: [link to Honeycomb query]

## Query Patterns

- **Time Range**: 1200 seconds (20 minutes) - adjustable based on when the test started

### Pattern 1: Get a particular trace

What service are you testing? This determines the dataset.
Do you know the name of the span you expect to see?

```
Query for:
- dataset: [dataset]
- filter: name = [expected span name]
- time_range: [calculated time range]
- calculation: COUNT
- include_samples: true
```

Now take the most recent sample, and use get_trace to get the full trace.
Output:

Queried [CALCULATION] where [FILTERS] over [TIME_RANGE]
Found [count] results
Results: [link to the query]

Most recent trace: [link to the trace]
Root span: [root span name]
Total spans: [count of spans]
Services: [list of services]

### Pattern 2: Find all traces since the test started

```
Query for:
- all datasets
- filter: trace.parent_id does-not-exist
- time_range: [calculated time range]
- calculation: COUNT
- breakdowns: name
- include_samples: true
```

Output:
Queried [CALCULATION] where [FILTERS] by [BREAKDOWNS] over [TIME_RANGE]
Found [count] results
Results: [link to the query]

For each sample, print:

- Trace ID
- Span name
- anything else it gives you
  Construct a link to the trace in Honeycomb, according to:
  https://ui.honeycomb.io/modernity/environments/personal-agent/trace?trace_id=[<traceId>]
  &trace_start_ts=[test_start_time]
  &trace_end_ts=[((date +%s))]

### Pattern 3: Find the most recent trace, precisely

```
Query for:
  calculated_fields: event_time=EVENT_TIMESTAMP()
  calculation: COUNT
  breakdowns: event_time, trace.trace_id
  order: event_time DESC
  limit: 1
  include_samples: false
```

Print the summary of the trace, as in Pattern 1.

Take the output trace_id and use get_trace to get the full trace.

### Pattern 4: When you don't see any traces, try: Get the time range right

Before running a test that will generate a trace, print the current time.

start_time=$(date +%s)

Then run the test to create the trace.

Then calculate the correct time range:

echo $(( $(date +%s) - $start_time + 20))

Include that in the query you're using to find traces.
