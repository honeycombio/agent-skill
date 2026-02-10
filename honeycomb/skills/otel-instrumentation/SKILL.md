---
name: otel-instrumentation
description: >
  This skill should be used when the user asks to "instrument my app", "add tracing",
  "set up OpenTelemetry", "configure OTel", "add custom spans", "add attributes to spans",
  "send traces to Honeycomb", "set up OTLP", "configure the OTel SDK",
  "add span events", "add span links", "instrument with OpenTelemetry",
  "set up tracing for Go", "set up tracing for Python", "set up tracing for Node.js",
  "set up tracing for Java", "set up tracing for Ruby", "set up tracing for .NET",
  "add observability", "improve instrumentation", "configure sampling",
  "set up head sampling", "set up tail sampling", "configure the OTel Collector",
  or needs guidance on OpenTelemetry SDK setup, custom instrumentation, or sending data to Honeycomb.
  After instrumenting, use the query-patterns skill to verify data is arriving.
metadata:
  version: "1.0.0"
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

## SDK Quick Start by Language

### Go
```go
import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
    "go.opentelemetry.io/otel/sdk/trace"
)
// Setup: otlptracehttp exporter + trace.NewTracerProvider
// Set env vars: OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_EXPORTER_OTLP_HEADERS, OTEL_SERVICE_NAME
```

### Python
```python
# pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
# Setup: TracerProvider + BatchSpanProcessor + OTLPSpanExporter
```

### Node.js
```javascript
// npm install @opentelemetry/sdk-node @opentelemetry/exporter-trace-otlp-http
const { NodeSDK } = require("@opentelemetry/sdk-node");
const { OTLPTraceExporter } = require("@opentelemetry/exporter-trace-otlp-http");
// Setup: new NodeSDK({ traceExporter: new OTLPTraceExporter() })
```

### Java
```
// Use OpenTelemetry Java Agent (auto-instrumentation):
// java -javaagent:opentelemetry-javaagent.jar -jar your-app.jar
// Set env vars for OTLP exporter configuration
```

For complete setup per language (including Ruby, .NET, Rust), consult `${CLAUDE_PLUGIN_ROOT}/skills/otel-instrumentation/references/sdk-setup-by-language.md`.

## Custom Instrumentation

### Adding Attributes to Existing Spans

The highest-impact custom instrumentation. No new spans — just add business context:

**Go:**
```go
span := trace.SpanFromContext(ctx)
span.SetAttributes(
    attribute.String("user.id", userID),
    attribute.String("tenant.name", tenantName),
    attribute.Int("cart.item_count", itemCount),
)
```

**Python:**
```python
span = trace.get_current_span()
span.set_attribute("user.id", user_id)
span.set_attribute("tenant.name", tenant_name)
```

**Node.js:**
```javascript
const span = trace.getActiveSpan();
span.setAttribute("user.id", userId);
span.setAttribute("tenant.name", tenantName);
```

### Creating Custom Spans

Wrap important operations for visibility in the trace waterfall:

**Go:**
```go
tracer := otel.Tracer("my-service")
ctx, span := tracer.Start(ctx, "process-checkout")
defer span.End()
span.SetAttributes(attribute.String("order.id", orderID))
```

**Python:**
```python
tracer = trace.get_tracer("my-service")
with tracer.start_as_current_span("process-checkout") as span:
    span.set_attribute("order.id", order_id)
```

**Node.js:**
```javascript
const tracer = opentelemetry.trace.getTracer("my-service");
tracer.startActiveSpan("process-checkout", (span) => {
    span.setAttribute("order.id", orderId);
    // ... do work ...
    span.end();
});
```

For full language-specific examples, consult `${CLAUDE_PLUGIN_ROOT}/skills/otel-instrumentation/references/custom-instrumentation.md`.

## What to Instrument

### High Value (Instrument First)
- API entry points (HTTP handlers, gRPC methods)
- Database queries (auto-instrumented by most SDKs)
- External HTTP calls (auto-instrumented by most SDKs)
- Message queue producers/consumers

### Medium Value (Add Next)
- Business logic operations (checkout, payment, fulfillment)
- Cache operations (hits, misses, evictions)
- Authentication and authorization checks
- Background job execution

### Attributes to Add
- **User context**: `user.id`, `user.role`, `tenant.id`
- **Business context**: `order.id`, `cart.value`, `feature.flag`
- **Deployment context**: `deployment.version`, `deployment.environment`
- **Request context**: Already added by auto-instrumentation (HTTP, gRPC fields)

## Span Events and Span Links

### Span Events
Record point-in-time events within a span (no duration):
```python
span.add_event("cache_miss", {"cache.key": key})
span.add_event("retry_attempt", {"attempt": 2, "reason": "timeout"})
```
**Use for**: Errors, retries, state changes, milestones within an operation.

### Span Links
Connect spans across different trace hierarchies:
```python
from opentelemetry.trace import Link
link = Link(other_span_context, attributes={"link.reason": "triggered_by"})
tracer.start_span("process-message", links=[link])
```
**Use for**: Async processing, fan-out/fan-in, cross-system correlation.

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
