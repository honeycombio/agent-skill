# SDK Setup by Language

Complete OpenTelemetry SDK setup instructions for each language, configured to send
traces to Honeycomb.

## Environment Variables (All Languages)

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="https://api.honeycomb.io"
export OTEL_EXPORTER_OTLP_HEADERS="x-honeycomb-team=YOUR_API_KEY"
export OTEL_SERVICE_NAME="your-service-name"
```

EU endpoint: `https://api.eu1.honeycomb.io`

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

See `${CLAUDE_PLUGIN_ROOT}/skills/otel-instrumentation/references/python.md` for the
full Python guide: package catalogue, ASGI programmatic setup, async SQLAlchemy,
middleware enrichment, and resource attributes.

### Quick start (WSGI apps only — Flask, Django)
```bash
pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-http \
            opentelemetry-distro
opentelemetry-instrument python app.py
```

**For ASGI apps (FastAPI, Starlette, NiceGUI) always use programmatic setup** — the
CLI runner doesn't integrate cleanly with ASGI lifespans. See the Python guide above.

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
