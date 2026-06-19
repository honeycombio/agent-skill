---
name: otel-instrumentation
description: >
  Provides guidance on OpenTelemetry SDK setup, custom instrumentation,
  and sending data to Honeycomb.
  Trigger phrases: "instrument my app", "add tracing",
  "set up OpenTelemetry", "configure OTel", "add custom spans",
  "add attributes to spans", "send traces to Honeycomb",
  "set up OTLP", "configure sampling", "add span events",
  "add span links", "set up tracing for [any language]",
  "configure the OTel Collector",
  or any request about OpenTelemetry SDK setup, custom instrumentation,
  or sending data to Honeycomb.
metadata:
  version: "1.0.0"
---

# OpenTelemetry Instrumentation

Highlevel overview of how to do Open Telemetry instrumentation:

1. Enable auto-instrumentation
2. Add service.version
3. Create weaver registry
4. Add business context instrumentation

## 1. Enable auto-instrumentation

Install the OpenTelemetry SDK plus the auto-instrumentation packages for the
app's language and frameworks (HTTP server, database client, etc.). Configure
the OTLP exporter to send to Honeycomb by setting `OTEL_EXPORTER_OTLP_ENDPOINT`
and an `OTEL_EXPORTER_OTLP_HEADERS` value containing your ingest key.

**Always set `service.name`.** Honeycomb uses `service.name` to name the dataset,
so traces are only grouped correctly when it is set — never leave it to default
(`unknown_service`). Prefer setting it via the `OTEL_SERVICE_NAME` environment
variable in the application's startup scripts (the launch command, entrypoint,
Dockerfile, systemd unit, Procfile, etc.) so it is applied consistently every
time the app starts. Derive the name deterministically rather than inventing one:
take it from the build configuration when available (e.g. the artifact/module
name in `pom.xml`, `build.gradle`, `package.json`, `pyproject.toml`, `go.mod`),
and otherwise fall back to the repository or project directory name. (Other
resource attributes that legitimately vary per environment — see step 2 — can
still come from `OTEL_RESOURCE_ATTRIBUTES`.)

**Opt into stable semantic conventions.** Auto-instrumentation libraries still
default to legacy attribute names (`http.method`, `http.status_code`,
`db.statement`, `db.system`, `net.peer.ip`, …). Set
`OTEL_SEMCONV_STABILITY_OPT_IN=http,database` (and pin recent instrumentation
versions) so spans use the current names (`http.request.method`,
`http.response.status_code`, `db.query.text`, `db.system.name`,
`network.peer.address`, …). Verify after first traffic that the new names appear.

## 2. Add service.version

Attach `service.version` to the resource so every span can be correlated to a
deploy. Source it from the build (git SHA, package version, or release tag) and
set it via `OTEL_RESOURCE_ATTRIBUTES=service.version=<value>` or in the
`Resource` you build in code. Add other stable resource attributes here too
(`deployment.environment.name`, `service.namespace`) when available.

## 3. Create weaver registry

Define a custom semantic-convention registry with
[OTel Weaver](https://github.com/open-telemetry/weaver) for the attributes your app
emits. The registry is the single source of truth for each attribute's name, type, and
meaning — giving consistent, well-typed names across the codebase and letting tooling
verify that emitted telemetry matches the contract.

Create it in a `weaver/` directory at the repository root:

- `weaver/manifest.yaml` — the registry manifest:

  ```yaml
  name: <app-name>
  description: Custom semantic conventions for <app-name>
  schema_url: https://<your-domain>/schemas/<app-name>/0.1.0
  ```

- one or more group files alongside it (e.g. `weaver/app.yaml`) declaring your
  attributes:

  ```yaml
  groups:
    - id: registry.app
      type: attribute_group
      brief: Custom application attributes
      attributes:
        - id: app.user.id
          type: string
          brief: Authenticated user id
          stability: development
          examples: ["u_123"]
  ```

Validate the registry before finishing, and fix anything it reports:

```
weaver registry check --registry weaver
```

Reference the registry-defined attribute names from your instrumentation (ideally via
generated constants) instead of hardcoding attribute-name strings, so the business
instrumentation in step 4 stays consistent and reviewable.

## 4. Add business context instrumentation

Auto-instrumentation captures the plumbing; this step captures the domain. Add
attributes for the entities and decisions that matter when debugging — user/
tenant IDs, order/cart IDs, feature flags, result counts, branch taken — onto
the active span, using the registry-defined names from step 3. Create custom
spans only for meaningful units of work not already covered by
auto-instrumentation, and record exceptions and outcomes so failures are
queryable.
