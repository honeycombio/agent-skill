---
name: otel-instrumentation
description: >
  Provides guidance on OpenTelemetry SDK setup, custom instrumentation,
  and sending data to Honeycomb.
  Trigger phrases: "instrument my app", "add tracing",
  "set up OpenTelemetry", "configure OTel", "add custom spans",
  "add attributes to spans", "send traces to Honeycomb",
  "set up OTLP", "configure sampling", "add span events",
  "add span links", "set up tracing for [any language]",
  "configure the OTel Collector",
  or any request about OpenTelemetry SDK setup, custom instrumentation,
  or sending data to Honeycomb.
metadata:
  version: "1.0.0"
---

# OpenTelemetry Instrumentation for Honeycomb

SDK setup, custom spans, attributes, span events, sampling, and layered telemetry.
For conceptual foundations (why wide events matter, how attributes connect to
investigation), see the **observability-fundamentals** skill.

## OTLP Configuration and SDK Setup

Every OTel SDK needs three environment variables to send data to Honeycomb:
`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`, and `OTEL_SERVICE_NAME`.

For the env var values, language-specific dependencies, and setup code (Go, Python,
Node.js, Java, Ruby, .NET, Rust), see
`${CLAUDE_PLUGIN_ROOT}/skills/otel-instrumentation/references/sdk-setup-by-language.md`.

## Custom Instrumentation

### Adding Attributes to Existing Spans (Highest Impact)

Add business context to auto-instrumented spans — no new spans needed. Get the current
span from context and call `SetAttributes` (Go), `set_attribute` (Python), or
`setAttribute` (Node.js) with user, tenant, business, and deployment context.

### Creating Custom Spans

Wrap important business operations for visibility in the trace waterfall. Use
`tracer.Start(ctx, "operation-name")` (Go), `tracer.start_as_current_span("operation-name")`
(Python), or `tracer.startActiveSpan("operation-name", callback)` (Node.js).

For full code examples in all languages, consult
`${CLAUDE_PLUGIN_ROOT}/skills/otel-instrumentation/references/custom-instrumentation.md`.

## When to Create a Span

Not every function needs a span. Two questions determine whether a span is worth creating:

1. **Is it interesting?** — Does the work meaningfully impact performance (latency or
   failures) for the overall request?
2. **Is it aggregable?** — If you group this span by name and attributes, will it produce
   useful trends and comparisons?

| Operation | Interesting? | Aggregable? | Create a Span? |
| :--- | :--- | :--- | :--- |
| HTTP request handler | Yes — variable latency, can fail | Yes — group by route, method, status | **Yes** |
| Database query | Yes — I/O bound, failure-prone | Yes — group by query type, table | **Yes** |
| External API call | Yes — network latency, dependencies | Yes — group by endpoint, status | **Yes** |
| Cache lookup | Yes — fast vs slow path | Yes — group by cache name, hit/miss | **Yes** |
| Message queue pub/consume | Yes — async boundary, delays | Yes — group by queue, message type | **Yes** |
| Business logic transaction | Yes — meaningful state change | Yes — group by type, outcome | **Yes** |
| Private helper function | No — trivial CPU, predictable | No — too granular | **No** |
| Loop iteration | Maybe — if slow | No — unbounded cardinality | **No** |
| Getter/setter | No — no meaningful duration | No — nothing to group by | **No** |
| Input validation (pure CPU) | No — fast, predictable | Maybe | **No** |
| Business logic orchestration | No — just calls instrumented code | No — duration is sum of children | **No** |

**Common mistakes:**
- **Too many spans**: A trace with millions of 2ms spans is far too detailed and rarely
  actionable. Roll them up — combine into a single span, or capture the detail as an
  attribute on the parent span instead.
- **Too few spans**: Collapsing hours of work into a single opaque handler leaves you
  guessing about where time is spent.
- **Test spans left in**: Spans named `test-span`, `debug-span`, or similar are
  artefacts that pollute the dataset. Remove any span created solely to verify tracing
  is working before finishing.

When in doubt, prefer **attributes on existing spans** over creating new child spans.

#### Timing Attributes (measure sub-operations without child spans)

Record important sub-operation durations as attributes on the parent span. These are
easier to query than child spans and work directly with BubbleUp.

```go
// Go: time auth and record on the existing span
span := trace.SpanFromContext(r.Context())
authStart := time.Now()
user, err := authenticate(r)
span.SetAttributes(attribute.Float64("auth.duration_ms", float64(time.Since(authStart).Milliseconds())))
```

```python
# Python: time auth and record on the existing span
span = trace.get_current_span()
auth_start = time.monotonic()
user = authenticate(request)
span.set_attribute("auth.duration_ms", (time.monotonic() - auth_start) * 1000)
```

#### Exception Slugs (tag each error site with a static identifier)

Tag each error throw site with a unique static string (`exception.slug`). This creates
a low-cardinality, greppable identifier that connects dashboards directly to code.

```go
// Go: static slug — greppable, safe for GROUP BY
span.SetAttributes(
    attribute.String("exception.slug", "err-stripe-charge-failed"),
    attribute.Bool("error", true),
)
span.RecordError(err)
```

```python
# Python: static slug — greppable, safe for GROUP BY
span.set_attribute("exception.slug", "err-stripe-card-error")
span.set_attribute("error", True)
span.record_exception(e)
```

Find unhandled errors (missing slugs): `WHERE error = true AND exception.slug does-not-exist`.

For extended examples in all languages, see
`${CLAUDE_PLUGIN_ROOT}/skills/otel-instrumentation/references/custom-instrumentation.md`.

## What to Instrument

### High Value (Instrument First)
- API entry points (HTTP handlers, gRPC methods)
- Database queries (auto-instrumented by most SDKs)
- External HTTP calls (auto-instrumented by most SDKs)
- Message queue producers/consumers

These are typically auto-instrumented by OTel SDKs and form the skeleton of your traces.

### Medium Value (Add Next)
- Business logic operations (checkout, payment, fulfillment)
- Cache operations (hits, misses, evictions)
- Authentication and authorization checks
- Background job execution

These are your business logic. Without custom spans here, you can see that a request was
slow but not *why* — the trace waterfall has gaps where the important work happens
invisibly.

### Attributes to Add

Attributes are the dimensions BubbleUp uses during investigations. Every attribute you
add is a new axis BubbleUp can diff on to find what's different about outlier requests.
For the complete catalog organized by category with rationale and example queries, see
`${CLAUDE_PLUGIN_ROOT}/skills/otel-instrumentation/references/wide-event-attributes.md`.

For why attributes matter conceptually, see the **observability-fundamentals** skill.

## Span Events and Span Links

- **Span events**: Record point-in-time occurrences within a span (errors, retries, state
  changes). Use `span.add_event("event_name", {attributes})`.
- **Span links**: Connect spans across different trace hierarchies (async processing,
  fan-out/fan-in, cross-system correlation). Create a `Link` to the related span context.

See `${CLAUDE_PLUGIN_ROOT}/skills/otel-instrumentation/references/custom-instrumentation.md`
for full examples of both patterns.

## Sampling

### Sampling Strategy

Sampling is about tradeoffs — there is no free lunch:

- **Head sampling favors cost over debuggability.** You save resources, but a 0.1% error
  at 1% sampling becomes effectively invisible. Head sampling is oblivious to what
  happens downstream.
- **Tail sampling favors fidelity over simplicity.** You keep interesting traces but need
  infrastructure (Refinery or Collector) to buffer and evaluate complete traces.

The math matters: if an error occurs 0.1% of the time and you head-sample at 1%, you'll
capture roughly 1 in 100,000 of those errors. At moderate traffic, that error may never
appear in your data.

### Head Sampling (SDK-level)
Decides whether to sample a trace at creation time. Simple but can miss interesting traces.
- Configure via `OTEL_TRACES_SAMPLER` env var
- `always_on` (default), `always_off`, `traceidratio` (e.g., sample 10%)
- `parentbased_traceidratio` respects parent sampling decisions
- **Best for:** Very high-throughput services where you can tolerate missing rare events

### Tail Sampling (Collector/Refinery)
Decides after the trace is complete. Keeps interesting traces (errors, slow requests).
- Use Honeycomb's **Refinery** for production tail sampling
- Or configure the OTel Collector's `tail_sampling` processor
- Can sample based on: latency, error status, specific attributes, trace duration
- **Best for:** Services where debuggability matters — keeps errors and outliers while
  sampling routine traffic

### Sampling Impact on Honeycomb
- Sampling reduces data volume and cost
- SLOs, BubbleUp, and query results adjust for sampling rate automatically
- Trace completeness may be affected — missing spans if not all services sample consistently
- Start with no sampling, then add as needed for cost management

## Layered Telemetry

OpenTelemetry is "trace-first" — context propagation is the glue that correlates all
signals. But effective observability layers multiple signal types for different purposes.

A three-question test for choosing the right signal:

1. **What needs causality and full-request context?** → Traces (spans)
2. **What needs inexpensive long-term storage and fast alerting?** → Metrics
3. **What is rare vs. common, and what are the audit requirements?** → Logs / events

**The histogram-alongside-spans pattern:** For high-throughput HTTP services, emit both a
span and a histogram metric for each handled request. This lets you head-sample traces
for cost while histograms provide last-ditch alerting — and exemplars link outlier metric
points back to specific traces for deeper investigation.

The technique is *layering* (not duplication) because each signal provides a different
view at a different level of detail.

For architectural patterns where layering is essential (streaming, async jobs, ETL), see
`${CLAUDE_PLUGIN_ROOT}/skills/otel-instrumentation/references/architectural-patterns.md`.

For AWS Lambda-specific patterns — choosing between the AWS Managed OTel Layer
and manual SDK setup, forceFlush, SDK 2.x setup, cross-Lambda trace propagation,
header normalisation, TOKEN vs REQUEST authorizers — see
`${CLAUDE_PLUGIN_ROOT}/skills/otel-instrumentation/references/lambda.md`.

## Logs in Honeycomb

OTel can send logs too. If you have existing log infrastructure, the OTel Collector can
ingest logs and forward them to Honeycomb as structured events:

- **OTel SDK log bridge**: Captures logs from your existing logging library (`slog` in Go,
  `logging` in Python, `winston`/`pino` in Node.js) and exports them as OTel log records.
- **OTel Collector `filelog` receiver**: Reads log files, parses them, exports as OTLP.

Logs sent through OTel arrive in Honeycomb as structured events with the same query
capabilities as spans.

## Naming Conventions

- **Span names**: Describe the operation (`HTTP GET /api/users`, `db.query SELECT`, `process-payment`)
- **Attribute names**: Use dot-separated namespaces (`user.id`, `order.total`, `cache.hit`)
- **Follow OTel semantic conventions** where applicable (`http.method`, `db.system`, `rpc.service`)
- **Custom attributes**: Use your own namespace (`app.`, `checkout.`, `mycompany.`)

## Additional Resources

### Reference Files
- **`${CLAUDE_PLUGIN_ROOT}/skills/otel-instrumentation/references/sdk-setup-by-language.md`** — OTLP configuration and SDK setup for Go, Python, Node.js, Java, Ruby, .NET, Rust
- **`${CLAUDE_PLUGIN_ROOT}/skills/otel-instrumentation/references/local-collector-debug-test.md`** — Run a local OTel Collector via Docker to verify spans, logs, and metrics without a Honeycomb account; includes `jq` commands for inspecting NDJSON output
- **`${CLAUDE_PLUGIN_ROOT}/skills/otel-instrumentation/references/custom-instrumentation.md`** — Custom instrumentation patterns with full code examples (timing attributes, exception slugs, async request summaries)
- **`${CLAUDE_PLUGIN_ROOT}/skills/otel-instrumentation/references/collector-config.md`** — OTel Collector configuration for format conversion, processing, and sampling
- **`${CLAUDE_PLUGIN_ROOT}/skills/otel-instrumentation/references/wide-event-attributes.md`** — Canonical attribute catalog organized by category with example queries
- **`${CLAUDE_PLUGIN_ROOT}/skills/otel-instrumentation/references/architectural-patterns.md`** — Trace design patterns for streaming, async, ETL, and serverless architectures
- **`${CLAUDE_PLUGIN_ROOT}/skills/otel-instrumentation/references/lambda.md`** — AWS Lambda: OTel Layer vs manual SDK setup trade-offs, forceFlush and per-request latency, SDK 2.x setup, cross-Lambda trace propagation, header normalisation, TOKEN vs REQUEST authorizer migration

### Cross-References
- For conceptual foundations of why wide events and attributes matter: **observability-fundamentals** skill
- After instrumenting, use the **query-patterns** skill to verify data is arriving
