# SDK Setup by Language

Complete OpenTelemetry SDK setup instructions for each language, configured to send
traces to Honeycomb.

## Environment Variables (All Languages)

### Required

```bash
export OTEL_SERVICE_NAME="your-service-name"
export OTEL_EXPORTER_OTLP_ENDPOINT="https://api.honeycomb.io"
export OTEL_EXPORTER_OTLP_HEADERS="x-honeycomb-team=YOUR_API_KEY"
```

EU endpoint: `https://api.eu1.honeycomb.io`

### Optional (Recommended)

```bash
# Protocol selection (default: http/protobuf)
export OTEL_EXPORTER_OTLP_PROTOCOL="http/protobuf"  # or "grpc"

# Signal-specific endpoints (override base endpoint)
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="https://api.honeycomb.io/v1/traces"
export OTEL_EXPORTER_OTLP_METRICS_ENDPOINT="https://api.honeycomb.io/v1/metrics"
```

### For Metrics (Required if sending metrics)

```bash
export OTEL_EXPORTER_OTLP_METRICS_HEADERS="x-honeycomb-team=YOUR_API_KEY,x-honeycomb-dataset=YOUR_METRICS_DATASET"
```

### Honeycomb Authentication Pitfall

The `x-honeycomb-team` header in `OTEL_EXPORTER_OTLP_HEADERS` is **required** for
Honeycomb to accept OTLP data. Without it, Honeycomb **silently rejects** requests — no
error is returned, data simply never appears.

A common mistake: the app has `HONEYCOMB_API_KEY` in `.env` but never sets
`OTEL_EXPORTER_OTLP_HEADERS`. The OTel SDK does NOT automatically read
`HONEYCOMB_API_KEY` — you must either:

1. Set `OTEL_EXPORTER_OTLP_HEADERS="x-honeycomb-team=YOUR_KEY"` explicitly, **or**
2. Pass headers programmatically when constructing exporters:
   ```typescript
   const headers = { "x-honeycomb-team": process.env.HONEYCOMB_API_KEY };
   new OTLPTraceExporter({ headers });
   new OTLPMetricExporter({ headers });
   ```

Also ensure `.env` is loaded (e.g., `import "dotenv/config"`) **before** the OTel SDK
initializes. In ESM/TypeScript, all imports resolve before module body code runs, so
`dotenv.config()` in the main file may execute too late.

### Honeycomb Metrics Dataset Header

Honeycomb requires the `x-honeycomb-dataset` header on the OTLP **metrics** endpoint to
route metrics to the correct dataset. Without it, metrics are silently dropped. Traces do
not require this header (they use `service.name` for routing).

```bash
export OTEL_EXPORTER_OTLP_METRICS_HEADERS="x-honeycomb-team=YOUR_API_KEY,x-honeycomb-dataset=YOUR_METRICS_DATASET"
```

Or pass `headers` with `x-honeycomb-dataset` programmatically when constructing the
metrics exporter.

## Go

### Dependencies
```bash
go get go.opentelemetry.io/otel \
       go.opentelemetry.io/otel/sdk/trace \
       go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp
```

### Auto-instrumentation libraries
```bash
go get go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp
go get go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc
```

### Notes
- Use `otelhttp.NewHandler()` to wrap HTTP handlers
- Use `otelgrpc.UnaryServerInterceptor()` for gRPC
- SDK reads env vars automatically

## Python

### Dependencies
```bash
pip install opentelemetry-sdk \
            opentelemetry-exporter-otlp-proto-http \
            opentelemetry-instrumentation-flask \
            opentelemetry-instrumentation-requests \
            opentelemetry-instrumentation-sqlalchemy
```

### Auto-instrumentation (recommended)
```bash
opentelemetry-instrument python app.py
```

### Programmatic setup
```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

resource = Resource.create({"service.name": "your-service"})
provider = TracerProvider(resource=resource)
processor = BatchSpanProcessor(OTLPSpanExporter())
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
```

## Node.js

### Dependencies
```bash
npm install @opentelemetry/sdk-node \
            @opentelemetry/exporter-trace-otlp-http \
            @opentelemetry/auto-instrumentations-node
```

### Setup (tracing.js — require before app)
```javascript
const { NodeSDK } = require("@opentelemetry/sdk-node");
const { OTLPTraceExporter } = require("@opentelemetry/exporter-trace-otlp-http");
const { getNodeAutoInstrumentations } = require("@opentelemetry/auto-instrumentations-node");

const sdk = new NodeSDK({
  traceExporter: new OTLPTraceExporter(),
  instrumentations: [getNodeAutoInstrumentations()],
});
sdk.start();
```

### Run
```bash
node --require ./tracing.js app.js
```

## Java

### Java Agent (recommended — zero code changes)
```bash
# Download agent jar
curl -L -o opentelemetry-javaagent.jar \
  https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/latest/download/opentelemetry-javaagent.jar

# Run with agent
java -javaagent:opentelemetry-javaagent.jar \
     -Dotel.exporter.otlp.endpoint=https://api.honeycomb.io \
     -Dotel.exporter.otlp.headers=x-honeycomb-team=YOUR_API_KEY \
     -Dotel.service.name=your-service \
     -jar your-app.jar
```

### Notes
- Java agent auto-instruments most frameworks (Spring, Servlet, JDBC, etc.)
- No code changes required for basic tracing
- Add custom spans via OTel API for business logic

## Ruby

### Dependencies
```ruby
# Gemfile
gem "opentelemetry-sdk"
gem "opentelemetry-exporter-otlp"
gem "opentelemetry-instrumentation-all"
```

### Setup
```ruby
require "opentelemetry/sdk"
require "opentelemetry/exporter/otlp"
require "opentelemetry/instrumentation/all"

OpenTelemetry::SDK.configure do |c|
  c.service_name = "your-service"
  c.use_all  # auto-instrument all supported libraries
end
```

## .NET

### Dependencies
```bash
dotnet add package OpenTelemetry.Extensions.Hosting
dotnet add package OpenTelemetry.Exporter.OpenTelemetryProtocol
dotnet add package OpenTelemetry.Instrumentation.AspNetCore
dotnet add package OpenTelemetry.Instrumentation.Http
```

### Setup (Program.cs)
```csharp
builder.Services.AddOpenTelemetry()
    .WithTracing(tracing => tracing
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddOtlpExporter());
```

## Rust

### Dependencies (Cargo.toml)
```toml
[dependencies]
opentelemetry = "0.21"
opentelemetry-otlp = { version = "0.14", features = ["http-proto"] }
opentelemetry_sdk = { version = "0.21", features = ["rt-tokio"] }
```

### Notes
- Rust uses OTLP exporter directly
- No auto-instrumentation; all spans are manual
- Use `tracing` crate with `tracing-opentelemetry` for ergonomic instrumentation

## Testing Locally Without Honeycomb

Before pointing your SDK at Honeycomb, verify that spans are being produced and
structured correctly using a local OTel Collector. Point your SDK at the local
collector instead of Honeycomb:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"
export OTEL_SERVICE_NAME="your-service"
# No OTEL_EXPORTER_OTLP_HEADERS needed — the local collector has no auth
```

Then start the collector:

```bash
./scripts/start-collector.sh --no-honeycomb
```

Spans appear in the debug output (stdout) and are written to `./otelcol-traces.ndjson`,
`./otelcol-logs.ndjson`, and `./otelcol-metrics.ndjson` on the host.

For full setup instructions, available flags, and `jq` commands for inspecting the
NDJSON output, see
`${CLAUDE_PLUGIN_ROOT}/skills/otel-instrumentation/references/local-collector-debug-test.md`.
