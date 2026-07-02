# Python

Concrete mechanics for instrumenting a Python app. Where this differs from the generic guidance in
the skill, **this file wins**. The skill's steps (gather → auto-instrument → standards → context →
registry → prove → hand back) still frame the work; this fills in the Python specifics.

## Choosing the path

- **Zero-code (`opentelemetry-instrument`)** — from `opentelemetry-distro`. Wraps the launch command
  (`opentelemetry-instrument uvicorn app:app …`) and wires traces, metrics, and logs from `OTEL_*`
  env with no code. Prefer it when the app has a plain entrypoint you control the launch of.
- **In-code SDK** — required when the process is started in a way you can't wrap, or an embedded
  server / framework (programmatic uvicorn, NiceGUI, Celery workers) builds its objects before the
  auto-instrumentor runs. Then wire the SDK explicitly and call your setup **first**, before the app
  imports modules that build engines/clients.

Discover installed instrumentations with `opentelemetry-bootstrap -l`; install with
`opentelemetry-bootstrap -a install`. Per-framework packages are
`opentelemetry-instrumentation-{fastapi,flask,django,sqlalchemy,psycopg,requests,…}`.

## service.name — set it in code for an SDK setup

For an in-code SDK, put `service.name` in the `Resource` **in code** as a fall-back. Do **not** rely solely on

```python
resource = Resource.create({
    "service.name": os.getenv("OTEL_SERVICE_NAME", "<service>"),
    "service.version": "<ver>",
})
```

(With the zero-code `opentelemetry-instrument` agent you have no Resource in code — there
`OTEL_SERVICE_NAME` in the launch script is the path, and it must actually be set.)

## Wire all three pipelines

Each signal is a provider + processor/reader + OTLP exporter, set as the global provider:

- **Traces** — `TracerProvider(resource=…)` + `BatchSpanProcessor(OTLPSpanExporter())` → `trace.set_tracer_provider(...)`
- **Metrics** — `MeterProvider(resource=…, metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter())])` → `metrics.set_meter_provider(...)`
- **Logs** — `LoggerProvider(resource=…)` + `BatchLogRecordProcessor(OTLPLogExporter())` → `set_logger_provider(...)`

Match the exporter package to the endpoint protocol: `opentelemetry-exporter-otlp-proto-http` for
Honeycomb's OTLP/HTTP (the HTTP exporter appends `/v1/{traces,metrics,logs}` itself), or
`-proto-grpc` for a gRPC collector.

## Logs are the usual casualty

A `LoggerProvider` + exporter exports nothing until the app's **real logger is bridged into it**:

- **stdlib `logging`** — attach `LoggingHandler(logger_provider=…)` to the root logger.
- **loguru / structlog** — add a sink/processor that re-emits records through a stdlib logger that
  carries the handler (or through the handler directly).

`LoggingInstrumentor().instrument(set_logging_format=True)` only injects trace IDs into log **text**
(correlation) — it does **not** export logs. Enabling only that, or standing up the `LoggerProvider`
without attaching the handler, are the two "looks done, exports zero records" traps. With
`opentelemetry-instrument`, set `OTEL_LOGS_EXPORTER=otlp` — logging auto-instrumentation then
attaches the handler for you.

## Import-order trap

The SDK and framework instrumentation must be in place **before** the instrumented objects are
created. Prefer the explicit hooks — `FastAPIInstrumentor.instrument_app(app)`,
`SQLAlchemyInstrumentor().instrument(engine=engine)` — and call your `setup_telemetry()` at the very
top of the entrypoint, before importing modules that construct the app, engine, or clients. For an
async SQLAlchemy engine, instrument its underlying `engine.sync_engine`.
