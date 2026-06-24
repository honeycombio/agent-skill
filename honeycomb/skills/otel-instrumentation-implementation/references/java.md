# Java — configuration

The easy case: use the **OpenTelemetry Java agent** and configure everything via env/JVM args. Don't
hand-write SDK/exporter setup in code — the agent does it and honors the standard env vars.

## Attach the agent
Add `-javaagent:/path/opentelemetry-javaagent.jar` to the launch command (start script, `JAVA_TOOL_OPTIONS`,
Dockerfile `ENTRYPOINT`, systemd unit). Pin the agent to the latest release. With the agent attached,
HTTP server, DB client, and many libraries are instrumented automatically across **all three signals**.

## Configuration is env-driven — keep it out of code
- **Transport:** the agent honors `OTEL_EXPORTER_OTLP_PROTOCOL` / `OTEL_EXPORTER_OTLP_ENDPOINT`. Don't
  construct exporters in code — there's nothing to hardcode and nothing to get wrong.
- **service.name:** `OTEL_SERVICE_NAME` (or `OTEL_RESOURCE_ATTRIBUTES=service.name=…`). Set it in the
  launch config so every start is consistent.
- **All three signals:** on by default; leave `OTEL_{TRACES,METRICS,LOGS}_EXPORTER` at `otlp` (never
  `none`). For logs, the agent's Logback/Log4j appender exports application logs as OTLP — keep it enabled.
- **Stable semconv:** `OTEL_SEMCONV_STABILITY_OPT_IN=http,database`.

## Don't fight the agent
Avoid adding a second SDK setup in code alongside the agent — duplicate providers/exporters cause
double export or conflicting resources. Configure through the agent's env vars and `-Dotel.*` system
properties instead.
