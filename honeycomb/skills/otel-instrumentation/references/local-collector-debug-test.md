# Local OTel Collector for Migration Verification

Running a local OTel Collector during migration lets you verify that spans are being
produced and structured correctly without needing a live Honeycomb account or sending
data to a remote backend. Useful for the early phases of migration (SDK init, middleware,
context propagation) where you just need to confirm telemetry is flowing.

The skill ships a script at `${CLAUDE_PLUGIN_ROOT}/scripts/start-collector.sh` that starts
the collector via Docker with a pre-built config.

## Starting the Collector

**Without Honeycomb (local verification only):**

```bash
./scripts/start-collector.sh --no-honeycomb
```

No API key required. Spans are printed to stdout and written to `./otelcol-spans.ndjson`.

**With Honeycomb (verify locally and forward to backend):**

```bash
./scripts/start-collector.sh --api-key YOUR_API_KEY
# or
HONEYCOMB_API_KEY=YOUR_API_KEY ./scripts/start-collector.sh
```

**Custom log file location:**

```bash
./scripts/start-collector.sh --no-honeycomb --log-file /tmp/my-service-spans.ndjson
```

**Custom collector config (bypasses all default flags):**

```bash
./scripts/start-collector.sh --config ./my-collector-config.yaml
```

The collector listens on `localhost:4317` (gRPC) and `localhost:4318` (HTTP). Point your
SDK at either:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318  # HTTP
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317  # gRPC
```

## Reading the Debug Output

The `debug` exporter prints a human-readable block for each span to stdout as it arrives.
Key fields to check during migration:

```
ResourceSpans #0
Resource attributes:
     -> service.name: Str(my-service)        ← confirms SDK is setting service name
ScopeSpans #0
Span #0
    Trace ID       : 0af7651916cd43dd8448eb211c80319c
    Parent ID      : b7ad6b7169203331          ← non-empty = span is connected to a parent
    ID             : c5e2f3a1b4d67890
    Name           : GET /api/orders
    Kind           : Server
    Start time     : ...
    End time       : ...
    Status code    : Ok
Attributes:
     -> http.method: Str(GET)
     -> http.route:  Str(/api/orders)
     -> http.status_code: Int(200)
```

**What to look for:**

| Field | What it tells you |
| :--- | :--- |
| `service.name` present | SDK resource is configured correctly |
| `Parent ID` non-empty | Context is propagating; span is connected to a parent |
| `Parent ID` empty | Span is a root — expected for entry points, a bug for internal spans |
| `http.route` present | Framework middleware is installed and working |
| `Status code: Error` | `span.SetStatus` is being called on error paths |

## Reading the NDJSON Log File

Each line in `otelcol-spans.ndjson` is one batch of spans serialised as OTLP JSON. To
inspect individual spans, use `jq`:

```bash
# Pretty-print all spans
jq . otelcol-spans.ndjson

# List all span names received
jq -r '.resourceSpans[].scopeSpans[].spans[].name' otelcol-spans.ndjson

# Check for disconnected spans (missing parentSpanId)
jq '.resourceSpans[].scopeSpans[].spans[] | select(.parentSpanId == null or .parentSpanId == "") | .name' \
  otelcol-spans.ndjson

# List all attribute keys seen across all spans
jq -r '.resourceSpans[].scopeSpans[].spans[].attributes[].key' otelcol-spans.ndjson | sort -u
```

## Stopping the Collector

`Ctrl+C` — the script traps the signal, stops the container, and removes the temporary
config file. The NDJSON log file is kept so you can inspect it after shutdown.
