# Go

Concrete mechanics for instrumenting a Go app. Where this differs from the generic guidance in the
skill, **this file wins**. The skill's steps still frame the work; this fills in the Go specifics.

## There is no zero-code agent

Go is compiled — there's no runtime agent or monkey-patching, so you **always wire the SDK in code**.
(eBPF-based auto-instrumentation exists but is infra-level and out of scope here.) Keep it minimal by
leaning on the contrib instrumentation wrappers rather than hand-rolling spans.

Packages: `go.opentelemetry.io/otel`, `go.opentelemetry.io/otel/sdk`, and OTLP exporters
`.../exporters/otlp/otlptrace/otlptracehttp`, `.../otlpmetric/otlpmetrichttp`,
`.../otlplog/otlploghttp`. Instrumentation from `go.opentelemetry.io/contrib/instrumentation/…`:
`net/http/otelhttp`.
`go get` any relevant packages for libraries that are used and commit `go.mod` / `go.sum`.

## service.name — set it in code *and* read the env

Do **both** — they aren't alternatives. `WithFromEnv()` reads `OTEL_SERVICE_NAME` (and
`OTEL_RESOURCE_ATTRIBUTES`), so an operator's env is honoured when present; the in-code
`semconv.ServiceName(...)` guarantees a valid name when it isn't — otherwise an unset env silently
yields `unknown_service:go` and the telemetry lands in the wrong dataset.

```go
res, _ := resource.New(ctx,
    resource.WithAttributes(semconv.ServiceName("<service>")),  // guaranteed floor
    resource.WithFromEnv(),                 // reads OTEL_SERVICE_NAME + OTEL_RESOURCE_ATTRIBUTES when set
)
```

Detectors merge **in order, last-wins on conflict**. With `WithFromEnv()` last (as above), a set
`OTEL_SERVICE_NAME` overrides the code value, while the code value remains the fallback when the env
is empty — `WithFromEnv()` returns nothing for an unset var, so it can't clobber your floor. (Swap
the order if you want the code value to always win.)

## Wire all three providers — and shut them down

Set each global provider, then register a flush on exit. Go's batch processors buffer, so **without a
`Shutdown` the final batch is lost** — the classic "ran fine, no telemetry" Go bug:

- `sdktrace.NewTracerProvider(WithResource(res), WithBatcher(traceExp))` → `otel.SetTracerProvider(tp)`
- `sdkmetric.NewMeterProvider(WithResource(res), WithReader(sdkmetric.NewPeriodicReader(metricExp)))` → `otel.SetMeterProvider(mp)`
- `sdklog.NewLoggerProvider(WithResource(res), WithProcessor(sdklog.NewBatchProcessor(logExp)))` → `global.SetLoggerProvider(lp)`
- `defer tp.Shutdown(ctx)` (and mp/lp) in `main`.

Set the propagator for W3C headers:
`otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(propagation.TraceContext{}, propagation.Baggage{}))`.

## Context propagation is manual — the rootless-trace trap

Go threads `context.Context` explicitly. A custom span **must** be started from the incoming
request's context (the one `otelhttp`/`otelgin` put the server span into), or it starts a brand-new,
parentless trace — an orphan/rootless span:

```go
ctx := r.Context()                     // carries the active server span
ctx, span := tracer.Start(ctx, "work") // nests correctly
defer span.End()
```

Never start a span from `context.Background()` inside a request path, and pass `ctx` down through the
call chain (including into DB calls, e.g. `db.WithContext(ctx)`), so spans link into one trace.

Threading `ctx` through a call graph is **one refactor, not a build-fix loop**. Adding a
`context.Context` parameter to a function breaks *every* caller, and `go build`/`go vet` will surface
them one layer at a time — so enumerate the whole set up front instead of chasing errors edit by edit.
Before you start editing, grep for every caller of the functions you're threading through — including
the ones that are easy to forget: **`*_test.go` files**, `AutoMigrate`/setup helpers, and callers in
other packages. Edit them all in one pass, then build **once**. A single planned sweep replaces a long
patch→`vet`→patch→`vet` cycle.

## Logs — bridge the app's real logger

A `LoggerProvider` exports nothing until the app's logger is routed through a bridge:

- **`log/slog`** — `go.opentelemetry.io/contrib/bridges/otelslog` (`otelslog.NewLogger` / `NewHandler`).
- **logrus / zap** — `otellogrus` / `otelzap` bridges.

Standing up the provider without swapping the app onto the bridged logger means no logs are exported.