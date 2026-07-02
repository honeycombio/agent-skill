# Java

Concrete mechanics for instrumenting a JVM app. Where this differs from the generic guidance in the
skill, **this file wins**. The skill's steps still frame the work; this fills in the Java specifics.

## Use the zero-code Java agent

Strongly prefer the OpenTelemetry Java **agent** (`opentelemetry-javaagent.jar`) over any in-code
SDK. Attaching it auto-instruments traces, metrics, **and** logs across the whole ecosystem
(Servlet/Spring/JAX-RS, JDBC/Hibernate, HTTP clients, messaging) with no source changes:

```
java -javaagent:/path/opentelemetry-javaagent.jar -jar app.jar
```

Configure entirely through env / system properties: `OTEL_SERVICE_NAME`,
`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS` (e.g. `x-honeycomb-team=<key>`), and
`OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf` for Honeycomb's OTLP/HTTP endpoint.

## service.name lives in the launch script

The agent owns the `Resource` — there is **no** code path to set `service.name`. So
`OTEL_SERVICE_NAME` (or `-Dotel.service.name=…`) **must** be present in the actual launch
command/script; if it's missing the service reports as `unknown_service:java` and lands in the wrong
dataset. Treat putting it in the startup script as mandatory, not optional, and note it in the
hand-back.

## All three signals ship by default

The agent exports traces, metrics, and logs out of the box. Logs flow via the Logback / Log4j2
appender instrumentation (enabled by default) — no bridge code needed. If logs don't arrive, confirm
`OTEL_LOGS_EXPORTER` is `otlp` (the default) and the appender instrumentation hasn't been disabled
(`otel.instrumentation.logback-appender.enabled` / `…log4j-appender…`).

## Do NOT add the SDK or exporters as dependencies

With the agent, the runtime SDK is provided **by the agent**. Adding
`opentelemetry-sdk`/`opentelemetry-exporter-*` as project dependencies creates a second,
unconfigured SDK and is a common source of "no telemetry" / duplicate-provider bugs. For custom
spans and attributes, add **only the API** as a compile dependency:

- `io.opentelemetry:opentelemetry-api` — `GlobalOpenTelemetry.getTracer(...)`, `Span.current()`.
- `io.opentelemetry.instrumentation:opentelemetry-instrumentation-annotations` — the `@WithSpan` /
  `@SpanAttribute` annotations (the agent weaves them at runtime).

The agent jar itself is not a build dependency — document the `-javaagent` flag in the run script and
report; the API goes in `pom.xml` / `build.gradle`.

## Semantic-convention opt-in

Move HTTP/DB instrumentation onto stable conventions with `OTEL_SEMCONV_STABILITY_OPT_IN` (`http`,
`database`, or the `…/dup` variants during migration). The agent tracks the conventions closely, so
**upgrading the agent jar to the latest release** is the main lever for staying current — do that
before concluding a convention gap is unfixable.
