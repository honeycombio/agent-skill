---
name: otel-instrumentation-implementation
description: >
  Implementation playbook for APPLYING OpenTelemetry instrumentation to an application — the
  concrete steps: enable auto-instrumentation and opt into stable semantic conventions, add
  service.version, create a weaver registry, add business-context spans, and set/communicate the
  required environment-variable contract. This is the "how to actually write the instrumentation"
  reference, used by the instrumenter role. For running a full engagement (coordinating
  implementation with independent verification), use the `otel-instrumentation` skill instead.
metadata:
  version: "1.0.0"
---

# OpenTelemetry Instrumentation — Implementation

This is the **implementation playbook**: apply these steps to instrument the target application.
You are the implementer. Coordinating the engagement (pairing this with independent verification)
is the `otel-instrumentation` skill's job — here you just implement well. Your work will be checked
against the `otel-verification` contract, so make sure the emitted telemetry actually holds up
(stable semantic-convention names present, legacy names absent, `service.name`/`service.version`
on the resource, business attributes present, connected traces, exceptions recorded).

## Required environment variables

Several settings must be **real environment variables set in the runtime environment
before the process (or language agent) starts** — not assigned from inside application
code. Instrumentation libraries read these once at initialization, often before your
own code runs, so setting them in-process (`os.environ`, `os.Setenv`, `System.setProperty`)
is unreliable. Set them in the launch command, entrypoint, start script, Dockerfile,
systemd unit, Procfile, or your platform's env/secrets config.

| Variable | Purpose | Where to set | Commit to source? |
|---|---|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP export target (Honeycomb, or a local/internal collector) | launch env / container env | yes |
| `OTEL_EXPORTER_OTLP_HEADERS` | _Optional_ — auth for the endpoint (e.g. `x-honeycomb-team=…` when exporting straight to Honeycomb). Omit when exporting to an unauthenticated internal collector. | **secrets store / CI env** | **no — it's a secret** |
| `OTEL_SERVICE_NAME` | names the Honeycomb dataset (see step 1) | launch script | yes |
| `OTEL_RESOURCE_ATTRIBUTES` | `service.version`, `deployment.environment.name`, … (see step 2) | launch env (values may vary per env) | yes (keys) |
| `OTEL_SEMCONV_STABILITY_OPT_IN` | `http,database` — emit current semconv (see step 1) | launch script | yes |

When you finish instrumenting, **communicate this contract explicitly** — do not assume it will
be inferred:

- Set what you can in committed launch config (start script, Dockerfile, etc.) and say
  what you set and where.
- For anything that must be set by the operator (especially secrets), print a copy-pasteable
  block, e.g.:

  ```
  # Add to your launch environment before running:
  export OTEL_EXPORTER_OTLP_ENDPOINT=https://api.honeycomb.io
  # optional: auth for the endpoint; omit for an internal collector. Keep in secrets, not git.
  export OTEL_EXPORTER_OTLP_HEADERS="x-honeycomb-team=$HONEYCOMB_KEY"   
  # To use the latest semantic naming conventions where possible.
  export OTEL_SEMCONV_STABILITY_OPT_IN=http,database
  ```

## 1. Enable auto-instrumentation

Install the OpenTelemetry SDK plus the auto-instrumentation packages for the
app's language and frameworks (HTTP server, database client, etc.). Configure
the OTLP exporter to send to Honeycomb by setting `OTEL_EXPORTER_OTLP_ENDPOINT`
and an `OTEL_EXPORTER_OTLP_HEADERS` value containing your ingest key.

**Upgrade all OpenTelemetry dependencies to their latest versions.** Whether you
are adding OTel for the first time or building on existing instrumentation, pin
the SDK, exporters, and every auto-instrumentation/contrib package (and language
agents like the OTel Java agent) to the most recent release. Newer versions emit
the current semantic conventions, fix bugs, and support options older releases
ignore — stale dependencies are a common cause of missing or legacy-named
telemetry. After upgrading, rebuild and confirm the app still compiles and runs.

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

**Extend the latest OTel semantic conventions; don't reinvent them.** Build your
registry on top of the current [OTel semantic conventions](https://github.com/open-telemetry/semantic-conventions)
release rather than defining your own names for things they already cover. Reuse the
published attributes (`http.*`, `db.*`, `user.*`, etc.) wherever one fits, and reserve
custom attributes for genuinely app-specific concepts the conventions don't model. In
the manifest, declare the upstream registry as a dependency so weaver resolves against
it and flags any attribute that duplicates or conflicts with a standard one:

```yaml
dependencies:
  - name: otel
    # pin the latest semantic-conventions release
    registry_path: https://github.com/open-telemetry/semantic-conventions/archive/refs/tags/v1.39.0.zip[model]
```

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
