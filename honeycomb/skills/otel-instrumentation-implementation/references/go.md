# Go — configuration

Go has no auto-instrumentation agent: you wire the SDK in code, in `main()`, before the server
starts. The traps below are all about making that code-level config behave like the env-driven
config other languages get for free.

## Exporter / transport — use `autoexport`, never hardcode the transport
Use `go.opentelemetry.io/contrib/exporters/autoexport` for all three signals:

```go
spanExp, _  := autoexport.NewSpanExporter(ctx)   // honors OTEL_TRACES_EXPORTER + OTLP_PROTOCOL/ENDPOINT
reader, _   := autoexport.NewMetricReader(ctx)
logExp, _   := autoexport.NewLogExporter(ctx)
```

Do **not** import a fixed exporter (`otlptracegrpc` / `otlptracehttp`, etc.) — that pins the transport
and **ignores `OTEL_EXPORTER_OTLP_PROTOCOL`**, so it silently drops everything when the endpoint
speaks the other protocol. `autoexport` selects the exporter from the standard env vars.

## service.name — set a CODE DEFAULT, don't rely on the launch env
A compiled binary is often started directly (`./app`), with no wrapper script and no `.env` loaded —
so config you put only in a `run.sh`/`.env`/`.env.example` is simply absent at runtime. Honeycomb
routes traces/logs by `service.name`; if it's unset they land in `unknown_service` /
`unknown_log_source`, not your service's dataset.

Set `service.name` (and `service.version`) as **code defaults on the resource**, with `WithFromEnv()`
*after* so `OTEL_SERVICE_NAME` still overrides when provided:

```go
res, _ := resource.New(ctx,
    resource.WithAttributes(
        semconv.ServiceName("<deterministic-name>"),    // from go.mod module / repo name
        semconv.ServiceVersion(version),
    ),
    resource.WithFromEnv(),        // OTEL_SERVICE_NAME / OTEL_RESOURCE_ATTRIBUTES override the defaults
    resource.WithTelemetrySDK(), resource.WithProcess(), resource.WithHost(),
)
```

Pass that one `res` to **all three** providers (`WithResource(res)`) so every signal carries it.

## Init order & flush
- Call SDK setup before building the router; obtain instruments/tracers *after* `otel.Set*Provider`,
  or middleware captures a no-op provider.
- Return a `shutdown(ctx)` that flushes all three providers and call it on exit. A blocking server
  (`r.Run()`) won't run a bare `defer` on SIGTERM — wire `signal.NotifyContext` if the deployment
  relies on graceful-shutdown flushing. (Note: metric readers also export periodically; short-lived
  processes may need `OTEL_METRIC_EXPORT_INTERVAL` lowered to flush in time.)

## Instrumentation packages
Install the contrib packages for your HTTP framework and DB driver (e.g. `otelgin`, `otelhttp`,
GORM/database/sql instrumentation) — and the metric/log variants, not only tracing.
