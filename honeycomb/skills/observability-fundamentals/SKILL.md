---
name: observability-fundamentals
description: >
  Use when answering conceptual "why" questions about observability — explains the
  foundations of why Honeycomb works the way it does: wide structured events, high
  cardinality, the core analysis loop, events vs metrics vs logs, and how
  instrumentation decisions connect to debugging outcomes. Grounds recommendations
  in first principles rather than tool-specific how-to.
  Trigger phrases: "what is observability", "why observability", "why Honeycomb",
  "events vs metrics", "events vs logs", "what should I instrument", "why wide events",
  "what is high cardinality", "how does BubbleUp work", "core analysis loop",
  "what makes good instrumentation", "observability vs monitoring", "why not just use
  metrics", "why not just use logs", "what is an event", "what is a span",
  "why structured events", "what is dimensionality", "explain observability",
  or any conceptual or philosophical question about observability, events,
  instrumentation strategy, or why Honeycomb's approach differs from traditional monitoring.
metadata:
  version: "1.4.0"
---

# Observability Fundamentals

The conceptual backbone of Honeycomb's approach to observability. This skill explains
*why* things work the way they do — use it to ground recommendations in first principles
and to answer questions that aren't about specific tools or SDK setup.

## What Is Observability

Observability is the ability to ask arbitrary questions about your system's behavior
without knowing ahead of time what you'll need to ask. A system is observable when you
can explain what's happening inside it by examining what it produces on the outside —
without deploying new code or adding new instrumentation for each new question.

This is the key distinction from traditional monitoring: monitoring checks known conditions
("is CPU above 80%?"), while observability lets you explore unknown conditions ("why are
checkout requests from EU users on iOS 30% slower than yesterday, but only for premium
tier accounts?"). You can't set up a dashboard for a question you haven't thought of yet.

## Why Wide Structured Events

Everything in Honeycomb starts with **wide structured events**. A single event captures
the full context of a unit of work: who made the request, which endpoint, whether the
cache hit, what build version is running, how long it took, whether it errored, and any
business context relevant to the operation.

In OpenTelemetry terms, a **span** is a wide structured event. Each span has a name,
a duration, a status, and an arbitrary set of **attributes** — key-value pairs that
carry context. The wider the span (more attributes), the more questions you can answer
from it without re-deploying.

Wide events matter because:

- **Every attribute is a queryable dimension.** Adding `user.id` to a span means you
  can GROUP BY, filter, or BubbleUp on user identity — forever, without changing code.
- **Context travels together.** When you add `user.id`, `tenant.name`, `deployment.version`,
  and `cache.hit` to the same span, you can correlate them: "slow requests are from
  tenant X on version 2.3.1 with cache misses." Separate metrics can't do this.
- **The cost is the same.** Adding an attribute to an existing span is a single
  `span.SetAttribute()` call. The instrumentation effort is trivial; the analytical
  value is enormous.

## Events vs Metrics vs Logs

Events, metrics, and logs are three ways to record what your system does. They require
roughly the same effort to instrument, but they differ dramatically in analytical power.

**Structured events** (spans) carry full context. A single event might contain: endpoint,
user ID, tenant, response status, duration, cache hit/miss, deployment version, error
message, database query count. You can slice this event on any dimension at query time.

**Metrics** pre-aggregate context away. A counter like `http_requests_total{status=500}`
tells you errors are happening but not *which users*, *which tenants*, or *which deployment*
caused them. Adding more label dimensions causes combinatorial explosion (the **curse of
dimensionality**) — storage and cost grow exponentially. So in practice you keep metrics
low-cardinality, which means you lose the dimensions you need most during an incident.

**Unstructured logs** preserve context but bury it in text. `"ERROR: checkout failed for
user=abc123 tenant=acme"` contains the same fields as an event, but you can't GROUP BY
`user` or run BubbleUp across log lines without parsing. Structured logging helps, but
most log backends still lack the query engine to correlate arbitrary dimensions at scale.

The same instrumentation effort that produces a metric or log line can produce a wide
structured event — and the event gives you all three capabilities: you can count it
(metric), read it (log), and analyze it across dimensions (observability).

For a detailed comparison with code examples, see
`${CLAUDE_PLUGIN_ROOT}/skills/observability-fundamentals/references/events-vs-metrics-vs-logs.md`.

## High Cardinality and Dimensionality

**Cardinality** is the number of unique values a field can have. `user.id` might have
millions of values — that's high cardinality. `http.method` has a handful — that's low
cardinality.

**Dimensionality** is the number of distinct fields (columns) on your events. A span
with 50 attributes has high dimensionality.

Traditional metrics systems penalize both: high cardinality explodes storage costs, and
high dimensionality creates too many time series. This forces you to pre-decide which
dimensions matter — and during an incident, the dimension you need is always the one
you left out.

Honeycomb's storage engine works differently. It stores events (rows) independently and
aggregates at query time. Adding `user.id` with 10 million unique values doesn't create
10 million time series — it's just another column on each event. This means:

- **Fields like `user.id`, `order.id`, `request.url` are valuable, not expensive.**
  They're often the exact dimensions that identify root causes during incidents.
- **You don't need to pre-aggregate.** Ask for P99 latency grouped by user ID at query
  time, not at instrumentation time.
- **BubbleUp can search all dimensions automatically.** It compares outlier vs baseline
  distributions across every column — the more columns you have, the more likely it
  finds the differentiator.

## The Core Analysis Loop

Debugging in Honeycomb follows a loop:

1. **Define** — What's the question? "Why are checkout requests slow?" Start with a
   hypothesis or an alert.
2. **Visualize** — Run a query to see the shape of the problem. HEATMAP of duration,
   COUNT of errors grouped by service, P99 over time. This corresponds to
   **Step 2 (Characterize)** in the production-investigation workflow.
3. **Investigate** — Narrow down. BubbleUp compares outlier vs baseline across all
   dimensions to find what's different. This is **Step 3 (BubbleUp)** — the automated
   form of investigation. Then drill into individual traces for the full request
   story (**Step 4 — Traces**).
4. **Evaluate** — Confirm the hypothesis. Query with the suspected cause filtered in
   and out. If the metrics diverge, you've found it. This is
   **Step 5 (Verify)** in the investigation workflow.

Then loop: each answer raises new questions. "Tenant X is slow" leads to "why is
tenant X slow?" — another pass through the loop.

BubbleUp is the core analysis loop automated: it defines the comparison (outlier vs
baseline), visualizes the distributions, and surfaces the dimensions that differ. It
only works if your events have enough dimensions to diff on — which is why wide events
matter.

For the full investigation workflow that implements this loop with Honeycomb's tools,
see the **production-investigation** skill.

## How Instrumentation Connects to Investigation

Every attribute you add to a span is a dimension that BubbleUp can use to find root
causes during an incident. This is the direct link between instrumentation decisions
and debugging outcomes:

- **`user.id`** → BubbleUp can identify if a single user or tenant is affected
- **`deployment.version`** → BubbleUp can flag a bad deploy instantly
- **`feature.flag`** → BubbleUp can correlate issues with feature rollouts
- **`cache.hit`** → BubbleUp can spot cache-related performance regressions
- **`db.query`** → BubbleUp can find specific slow queries

**Instrument for the questions you'll ask at 3am, not for completeness.** During an
incident, you need to answer: Who is affected? What changed? Where is the bottleneck?
The attributes that answer those questions are the ones worth adding:

- **Who**: `user.id`, `tenant.name`, `user.role`, `plan.tier`
- **What changed**: `deployment.version`, `feature.flag`, `config.version`
- **Where**: business operation spans, database spans, cache spans, external call spans

If BubbleUp returns nothing useful during an investigation, the issue is usually an
instrumentation gap, not a BubbleUp limitation. The fix is to add the missing dimensions.

For hands-on guidance on adding instrumentation, see the **otel-instrumentation** skill.
For autonomous gap analysis, use the **instrumentation-advisor** agent.

## Additional Resources

### Reference Files
- **`${CLAUDE_PLUGIN_ROOT}/skills/observability-fundamentals/references/events-vs-metrics-vs-logs.md`** — Detailed comparison with code examples showing the same operation instrumented as an event, a metric, and a log

### Cross-References
- For SDK setup and custom instrumentation, see the **otel-instrumentation** skill
- For the investigation workflow that implements the core analysis loop, see the **production-investigation** skill
- For autonomous instrumentation gap analysis, use the **instrumentation-advisor** agent
