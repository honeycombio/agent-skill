# Bridge Libraries

Bridge libraries connect existing logging and metrics infrastructure to OpenTelemetry without
requiring you to rewrite existing instrumentation. They let you adopt OTel incrementally —
your existing Prometheus metrics and log statements continue to work while also flowing
through the OTel pipeline.

## Logging Bridges

Logging bridges connect existing logging frameworks to the OTel LoggerProvider, so log records
are exported alongside traces and metrics. Logs exported through OTel include trace and span IDs,
enabling correlation between logs and traces in your backend.

### Go: slog bridge

```bash
go get go.opentelemetry.io/contrib/bridges/otelslog
```

**Multi-handler pattern** — send logs to both stderr and OTel:

```go
import (
    "log/slog"
    "os"
    otelslog "go.opentelemetry.io/contrib/bridges/otelslog"
)

stderrHandler := slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: level})
otelHandler := otelslog.NewHandler("service-name")
slog.SetDefault(slog.New(&multiHandler{
    handlers: []slog.Handler{stderrHandler, otelHandler},
}))
```

The `multiHandler` must implement `slog.Handler` with `Enabled()`, `Handle()`,
`WithAttrs()`, and `WithGroup()` — each method delegates to all inner handlers.

**Migrating from other Go loggers:**

| From | Path | Notes |
|------|------|-------|
| slog | Direct bridge | Use `otelslog.NewHandler` |
| logr | Migrate to slog first | No direct OTel bridge for logr |
| logrus | `go.opentelemetry.io/contrib/bridges/otellogrus` | Direct bridge available |
| zap | `go.opentelemetry.io/contrib/bridges/otelzap` | Direct bridge available |
| log.Printf | Migrate to slog first | No bridge for stdlib log |

**Structured logging prerequisite:** OTel bridges require structured key-value pairs.
Convert printf-style calls:

```go
// WRONG — format string becomes the message, structured fields lost
slog.Info(fmt.Sprintf("found %d users", count))

// WRONG — %d is literal text, not formatted
slog.Info("found %d users", "count", count)

// RIGHT — structured key-value pairs
slog.Info("found users", "count", count)
```

### Python: logging bridge

```bash
pip install opentelemetry-sdk
```

The Python SDK includes a `LoggingHandler` for the stdlib `logging` module:

```python
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter

logger_provider = LoggerProvider()
logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))

handler = LoggingHandler(logger_provider=logger_provider)
logging.getLogger().addHandler(handler)
```

Python's `logging` module is already structured (supports `extra` dict), so conversion
is typically straightforward.

### Node.js: winston and pino bridges

**Winston:**
```bash
npm install @opentelemetry/winston-transport
```

```javascript
const { OpenTelemetryTransportV3 } = require('@opentelemetry/winston-transport');
const winston = require('winston');

const logger = winston.createLogger({
  transports: [
    new winston.transports.Console(),
    new OpenTelemetryTransportV3(),
  ],
});
```

**Pino:**
```bash
npm install @opentelemetry/pino-transport
```

```javascript
const pino = require('pino');
const logger = pino({
  transport: {
    targets: [
      { target: 'pino-pretty' },
      { target: '@opentelemetry/pino-transport' },
    ],
  },
});
```

### Java: Log4j and Logback bridges

**Log4j appender:**
```xml
<dependency>
    <groupId>io.opentelemetry.instrumentation</groupId>
    <artifactId>opentelemetry-log4j-appender-2.17</artifactId>
</dependency>
```

```xml
<!-- log4j2.xml -->
<Appenders>
    <OpenTelemetry name="otel" />
    <Console name="console" />
</Appenders>
<Loggers>
    <Root level="info">
        <AppenderRef ref="otel" />
        <AppenderRef ref="console" />
    </Root>
</Loggers>
```

**Logback appender:**
```xml
<dependency>
    <groupId>io.opentelemetry.instrumentation</groupId>
    <artifactId>opentelemetry-logback-appender-1.0</artifactId>
</dependency>
```

```xml
<!-- logback.xml -->
<appender name="otel" class="io.opentelemetry.instrumentation.logback.appender.v1_0.OpenTelemetryAppender" />
<root level="INFO">
    <appender-ref ref="otel" />
    <appender-ref ref="STDOUT" />
</root>
```

**Context correlation (MDC):** To include trace_id and span_id in log output (file/stdout),
add the context bridge:

| Logger | Context bridge artifact |
|--------|----------------------|
| Log4j | `opentelemetry-log4j-context-data-2.17-autoconfigure` |
| Logback | `opentelemetry-logback-mdc-1.0` |

### .NET: ILogger bridge

.NET uses `ILogger` natively. The OTel .NET SDK bridges it directly:

```csharp
builder.Services.AddOpenTelemetry()
    .WithLogging(logging => logging
        .AddOtlpExporter());
```

`ILogger` calls automatically include trace/span correlation when an `Activity` is current.

### Ruby: Logger bridge

Ruby's OTel SDK provides a logs SDK, but ecosystem bridge support is still maturing.
The current recommended approach is to use the OTel Collector's filelog receiver to
ingest log files, or to emit structured JSON logs that include trace context.

## Metrics Bridges

### Go: Prometheus bridge

```bash
go get go.opentelemetry.io/contrib/bridges/prometheus
```

The bridge reads from Prometheus's default registry and produces OTel metrics:

```go
import (
    prombridge "go.opentelemetry.io/contrib/bridges/prometheus"
    sdkmetric "go.opentelemetry.io/otel/sdk/metric"
)

promProducer := prombridge.NewMetricProducer()
meterProvider := sdkmetric.NewMeterProvider(
    sdkmetric.WithReader(
        sdkmetric.NewPeriodicReader(metricExporter,
            sdkmetric.WithInterval(30*time.Second),
            sdkmetric.WithProducer(promProducer),
        ),
    ),
    sdkmetric.WithResource(res),
)
```

Your existing `prometheus.NewCounterVec(...)` calls continue unchanged. The bridge exports
them via OTLP alongside any new OTel-native metrics.

**Key decisions:**
- Keep the `/metrics` endpoint if you have existing Prometheus scrapers
- The bridge adds OTLP export in addition to scraping, not instead of
- Use OTel SDK metric views to filter metrics you don't want exported via OTLP
- Plan Prometheus client removal as a separate future step if desired

### Java: Micrometer bridge

```xml
<dependency>
    <groupId>io.opentelemetry.instrumentation</groupId>
    <artifactId>opentelemetry-micrometer-1.5</artifactId>
</dependency>
```

Bridges Micrometer metrics (common in Spring Boot apps) into OTel. Existing
`meterRegistry.counter(...)` calls are exported via OTLP.

### Java: Prometheus client bridge

```xml
<dependency>
    <groupId>io.opentelemetry.contrib</groupId>
    <artifactId>opentelemetry-prometheus-client-bridge</artifactId>
</dependency>
```

Bridges the Prometheus Java client library metrics into OTel.

### Python: Prometheus exporter (reverse direction)

Python doesn't have a Prometheus-to-OTel bridge in the same sense. Instead, if you have
existing Prometheus metrics, the recommended path is:

1. Keep existing Prometheus client metrics for scraping
2. Add new metrics using the OTel Meter API
3. Or use the OTel Collector's Prometheus receiver to scrape your `/metrics` endpoint
   and convert to OTLP

### .NET: Prometheus bridge

.NET's OTel SDK can export metrics in Prometheus exposition format alongside OTLP:

```csharp
builder.Services.AddOpenTelemetry()
    .WithMetrics(metrics => metrics
        .AddPrometheusExporter()  // keep /metrics endpoint
        .AddOtlpExporter());     // also export via OTLP
```

### General: OTel Collector Prometheus receiver

For any language, the OTel Collector can scrape an existing Prometheus `/metrics` endpoint
and convert the metrics to OTLP:

```yaml
receivers:
  prometheus:
    config:
      scrape_configs:
        - job_name: 'my-service'
          scrape_interval: 30s
          static_configs:
            - targets: ['localhost:9090']

exporters:
  otlp:
    endpoint: "https://api.honeycomb.io:443"
    headers:
      x-honeycomb-team: "YOUR_API_KEY"

pipelines:
  metrics:
    receivers: [prometheus]
    exporters: [otlp]
```

This approach requires no code changes — just a Collector configuration.
