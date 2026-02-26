# Migration Steps by Language

Detailed Beeline-to-OTel migration instructions for each supported language.

## Go

### Before (Beeline)
```go
import "github.com/honeycombio/beeline-go"

func main() {
    beeline.Init(beeline.Config{
        WriteKey: "YOUR_API_KEY",
        Dataset:  "my-service",
        ServiceName: "my-service",
    })
    defer beeline.Close()
}
```

### After (OpenTelemetry)
```go
import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
    "go.opentelemetry.io/otel/sdk/resource"
    "go.opentelemetry.io/otel/sdk/trace"
    semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
)

func main() {
    exporter, _ := otlptracehttp.New(context.Background())
    tp := trace.NewTracerProvider(
        trace.WithBatcher(exporter),
        trace.WithResource(resource.NewWithAttributes(
            semconv.SchemaURL,
            semconv.ServiceName("my-service"),
        )),
    )
    otel.SetTracerProvider(tp)
    defer tp.Shutdown(context.Background())
}
```

### Field mapping
| Beeline | OTel |
|---------|------|
| `beeline.AddField(ctx, "key", val)` | `span.SetAttributes(attribute.String("key", val))` |
| `beeline.StartSpan(ctx, "name")` | `tracer.Start(ctx, "name")` |
| `span.Send()` | `span.End()` |

## Python

### Before (Beeline)
```python
import beeline
beeline.init(writekey="YOUR_API_KEY", dataset="my-service", service_name="my-service")
```

### After (OpenTelemetry)
```python
# Set env vars: OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_EXPORTER_OTLP_HEADERS, OTEL_SERVICE_NAME
# Use auto-instrumentation: opentelemetry-instrument python app.py
# Or configure programmatically (see otel-instrumentation skill)
```

### Field mapping
| Beeline | OTel |
|---------|------|
| `beeline.add_field("key", val)` | `span.set_attribute("key", val)` |
| `beeline.tracer.start_span({"name": "op"})` | `tracer.start_as_current_span("op")` |
| `span.send()` | Context manager handles `span.end()` |

## Node.js

### Before (Beeline)
```javascript
const beeline = require("honeycomb-beeline")({
    writeKey: "YOUR_API_KEY",
    dataset: "my-service",
    serviceName: "my-service",
});
```

### After (OpenTelemetry)
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

### Field mapping
| Beeline | OTel |
|---------|------|
| `beeline.addContext({ key: val })` | `span.setAttribute("key", val)` |
| `beeline.startSpan({ name: "op" })` | `tracer.startActiveSpan("op", (span) => { ... })` |
| `beeline.finishSpan(span)` | `span.end()` |

## Java

### Before (Beeline)
```java
Beeline beeline = Beeline.getInstance(BeelineConfig.builder()
    .writeKey("YOUR_API_KEY")
    .dataset("my-service")
    .serviceName("my-service")
    .build());
```

### After (OpenTelemetry)
```bash
# No code changes needed — use Java Agent:
java -javaagent:opentelemetry-javaagent.jar \
     -Dotel.service.name=my-service \
     -jar your-app.jar
```

## Ruby

### Before (Beeline)
```ruby
Honeycomb.configure do |config|
  config.write_key = "YOUR_API_KEY"
  config.dataset = "my-service"
  config.service_name = "my-service"
end
```

### After (OpenTelemetry)
```ruby
require "opentelemetry/sdk"
require "opentelemetry/exporter/otlp"
require "opentelemetry/instrumentation/all"

OpenTelemetry::SDK.configure do |c|
  c.service_name = "my-service"
  c.use_all
end
```
