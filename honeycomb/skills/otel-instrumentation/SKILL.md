---
name: otel-instrumentation
description: >
  Use when the user asks to "instrument my app", "add tracing",
  "set up OpenTelemetry", "configure OTel", "add custom spans", "add attributes to spans",
  "send traces to Honeycomb", "set up OTLP", "configure the OTel SDK",
  "add span events", "add span links", "instrument with OpenTelemetry",
  "set up tracing for Go", "set up tracing for Python", "set up tracing for Node.js",
  "set up tracing for Java", "set up tracing for Ruby", "set up tracing for .NET",
  "add observability", "improve instrumentation", "configure sampling",
  "set up head sampling", "set up tail sampling", "configure the OTel Collector",
  or needs guidance on OpenTelemetry SDK setup, custom instrumentation, or sending data to Honeycomb.
metadata:
  version: "1.4.0"
---

# OpenTelemetry Instrumentation for Honeycomb

Guide to instrumenting applications with OpenTelemetry to send traces to Honeycomb.
Covers SDK setup, OTLP configuration, custom spans, attributes, span events, and sampling.

## OTLP Configuration (All Languages)

Every OTel SDK needs three environment variables to send data to Honeycomb:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="https://api.honeycomb.io"
export OTEL_EXPORTER_OTLP_HEADERS="x-honeycomb-team=YOUR_API_KEY"
export OTEL_SERVICE_NAME="your-service-name"
```

**EU endpoint**: `https://api.eu1.honeycomb.io`

**Important**: `OTEL_SERVICE_NAME` determines the dataset name in Honeycomb. Choose a
descriptive, stable name (e.g., `checkout-service`, not `my-app`).

## SDK Setup

The pattern is the same across languages: install the OTel SDK + OTLP exporter, create a
TracerProvider, and set the three env vars above. For language-specific setup (Go, Python,
Node.js, Java, Ruby, .NET, Rust), consult
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

## What to Instrument

### High Value (Instrument First)
- API entry points (HTTP handlers, gRPC methods)
- Database queries (auto-instrumented by most SDKs)
- External HTTP calls (auto-instrumented by most SDKs)
- Message queue producers/consumers

These are typically auto-instrumented by OTel SDKs and form the skeleton of your traces.
They give you the basic shape of every request — where time is spent across services,
databases, and external calls. Without them you have no trace structure at all.

### Medium Value (Add Next)
- Business logic operations (checkout, payment, fulfillment)
- Cache operations (hits, misses, evictions)
- Authentication and authorization checks
- Background job execution

These are your business logic. Without custom spans here, you can see that a request was
slow but not *why* — the trace waterfall has gaps where the important work happens
invisibly. A 2-second gap between an HTTP handler span and a database span means something
significant happened, but without a span covering it, you're guessing.

### Attributes to Add
- **User context**: `user.id`, `user.role`, `tenant.id`
- **Business context**: `order.id`, `cart.value`, `feature.flag`
- **Deployment context**: `deployment.version`, `deployment.environment`
- **Request context**: Already added by auto-instrumentation (HTTP, gRPC fields)

Attributes are the dimensions BubbleUp uses during investigations. Every `user.id`,
`tenant.name`, `feature.flag` you add is a new axis BubbleUp can diff on to find what's
different about outlier requests. Instrument for the questions you'll ask at 3am — "is
this one user?", "is this the new deploy?", "is this behind a feature flag?" — each of
those questions requires the corresponding attribute to exist on your spans.

For more on why attributes matter and how they connect to investigation workflows, see
the **observability-fundamentals** skill.

## Span Events and Span Links

- **Span events**: Record point-in-time occurrences within a span (errors, retries, state
  changes). Use `span.add_event("event_name", {attributes})`.
- **Span links**: Connect spans across different trace hierarchies (async processing,
  fan-out/fan-in, cross-system correlation). Create a `Link` to the related span context.

See `${CLAUDE_PLUGIN_ROOT}/skills/otel-instrumentation/references/custom-instrumentation.md`
for full examples of both patterns.

## Sampling

### Head Sampling (SDK-level)
Decides whether to sample a trace at creation time. Simple but can miss interesting traces.
- Configure via `OTEL_TRACES_SAMPLER` env var
- `always_on` (default), `always_off`, `traceidratio` (e.g., sample 10%)
- `parentbased_traceidratio` respects parent sampling decisions

### Tail Sampling (Collector/Refinery)
Decides after the trace is complete. Keeps interesting traces (errors, slow requests).
- Use Honeycomb's **Refinery** for production tail sampling
- Or configure the OTel Collector's `tail_sampling` processor
- Can sample based on: latency, error status, specific attributes, trace duration

### Sampling Impact on Honeycomb
- Sampling reduces data volume and cost
- SLOs, BubbleUp, and query results adjust for sampling rate automatically
- Trace completeness may be affected — missing spans if not all services sample consistently
- Start with no sampling, then add as needed for cost management

## Logs in Honeycomb

OTel isn't just for traces — it can send logs too. If you have existing log infrastructure,
the OTel Collector can ingest logs and forward them to Honeycomb as structured events:

- **OTel SDK log bridge**: Most OTel SDKs provide a log bridge that captures logs from
  your existing logging library (e.g., `slog` in Go, `logging` in Python, `winston`/`pino`
  in Node.js) and exports them as OTel log records.
- **OTel Collector `filelog` receiver**: Reads log files, parses them, and exports as OTLP.
- **Collector log pipeline**: Use the `filelog` or `otlp` receiver → processors for
  parsing, enriching, and filtering → `otlp` exporter to Honeycomb.

Logs sent through OTel arrive in Honeycomb as structured events with the same query
capabilities as spans. This is a good migration path if you have existing log pipelines
but want the analytical power of Honeycomb's query engine and BubbleUp.

## Naming Conventions

- **Span names**: Describe the operation (`HTTP GET /api/users`, `db.query SELECT`, `process-payment`)
- **Attribute names**: Use dot-separated namespaces (`user.id`, `order.total`, `cache.hit`)
- **Follow OTel semantic conventions** where applicable (`http.method`, `db.system`, `rpc.service`)
- **Custom attributes**: Use your own namespace (`app.`, `checkout.`, `mycompany.`)

## Additional Resources

### Reference Files
- **`${CLAUDE_PLUGIN_ROOT}/skills/otel-instrumentation/references/sdk-setup-by-language.md`** — Complete SDK setup for Go, Python, Node.js, Java, Ruby, .NET, Rust
- **`${CLAUDE_PLUGIN_ROOT}/skills/otel-instrumentation/references/custom-instrumentation.md`** — Detailed custom instrumentation patterns with full code examples
- **`${CLAUDE_PLUGIN_ROOT}/skills/otel-instrumentation/references/collector-config.md`** — OTel Collector configuration for format conversion, processing, and sampling

### Cross-References
- For the conceptual foundations of why wide events and attributes matter, see the **observability-fundamentals** skill
- After instrumenting, use the **query-patterns** skill to verify data is arriving in Honeycomb
