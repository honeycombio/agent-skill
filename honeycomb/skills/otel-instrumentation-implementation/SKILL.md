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

**Handed specific findings to fix?** (e.g. weaver violations from a prior verification cycle) Don't
re-run the whole flow — make a targeted fix against the existing instrumentation and stop. Skip to
**Fixing verifier findings** (the last section).

**Set OpenTelemetry config as real environment variables** — in the launch environment, **before the
process (or language agent) starts** (launch command, entrypoint, start script, Dockerfile, systemd
unit, Procfile). Instrumentation libraries read them once at initialization, often before your own code
runs, so assigning them in-process (`os.environ`, `os.Setenv`, `System.setProperty`) is unreliable. The
full set to set — and hand off to the operator — is in **Finish: communicate the env-var contract**.

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
the manifest, declare the upstream registry as a dependency:

```yaml
dependencies:
  - name: otel
    # pin the latest semantic-conventions release
    registry_path: https://github.com/open-telemetry/semantic-conventions/archive/refs/tags/v1.39.0.zip[model]
```

**Declaring the dependency isn't enough — you must `import` from it.** A `dependencies:` entry
doesn't merge the upstream attributes; without an `imports` block, every standard attribute your
auto-instrumentation emits (`http.request.method`, `db.query.text`, `server.address`, …) is reported
as *"does not exist in the registry"*. Pull in the upstream groups wholesale (don't enumerate by hand):

```yaml
# in a group file alongside `groups:` — makes the registry self-describing, so the
# standard attributes your telemetry emits resolve against it with no extra flags.
imports:
  attribute_groups:
    - registry.*    # build on every upstream semconv attribute group
```

Create it in a `weaver/` directory at the repository root:

- `weaver/manifest.yaml` — the registry manifest:

  ```yaml
  name: <app-name>
  description: Custom semantic conventions for <app-name>
  schema_url: https://<your-domain>/schemas/<app-name>/0.1.0
  ```

- one or more group files alongside it (e.g. `weaver/app.yaml`) — the `imports` block
  plus your custom attributes:

  ```yaml
  imports:
    attribute_groups:
      - registry.*
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

Keep custom attributes strictly under your own namespace (`app.*`). Never add an
attribute under a standard semconv namespace you import (`db.*`, `http.*`, `server.*`,
…) — e.g. don't invent `db.rows_affected`; use the standard attribute if one fits
(`db.response.returned_rows`) or namespace it as `app.*`. Defining your own attribute
inside an imported namespace collides with it and will be rejected at verification.

**Account for attributes your code doesn't set — in `weaver/libraries.yaml`.** The
registry must be a *complete* description of the telemetry the app emits, and
verification treats **any** undeclared attribute as a FAIL — including ones your code
never sets, emitted by an instrumentation library or the runtime (e.g. `asgi.event.type`
from ASGI instrumentation, framework-specific attributes). Standard semconv attributes
(`http.*`, `db.*`, `process.*`, `host.*`, …) are already covered by the `imports` block,
so they won't be flagged. For the rest — library/framework attributes that aren't in
semconv — declare them in a **separate** `weaver/libraries.yaml` group file, kept apart
from your own `app.*` attributes so it's clear which attributes the app authors versus
which it merely passes through:

```yaml
# weaver/libraries.yaml — attributes emitted by instrumentation libraries / the runtime
# (NOT set by app code) but present in the telemetry. Cataloguing them keeps the registry
# complete so weaver's missing_attribute checks pass. Do NOT list semconv attributes here
# (the imports block already covers those); only library/framework-specific ones.
groups:
  - id: registry.libraries
    type: attribute_group
    brief: Attributes emitted by instrumentation libraries / runtime, not set by app code
    attributes:
      - id: asgi.event.type
        type: string
        brief: ASGI event type emitted by the ASGI instrumentation
        stability: development
        examples: ["http.response.start", "http.response.body"]
```

You typically populate this reactively — see **Fixing verifier findings** below.

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

## Finish: communicate the env-var contract

When you finish, **communicate this contract explicitly** — don't assume it will be inferred. These
must be real environment variables, set before the process starts (see the note at the top):

| Variable | Purpose | Where to set | Commit to source? |
|---|---|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP export target (Honeycomb, or a local/internal collector) | launch env / container env | yes |
| `OTEL_EXPORTER_OTLP_HEADERS` | _Optional_ — auth for the endpoint (e.g. `x-honeycomb-team=…` when exporting straight to Honeycomb). Omit when exporting to an unauthenticated internal collector. | **secrets store / CI env** | **no — it's a secret** |
| `OTEL_SERVICE_NAME` | names the Honeycomb dataset (step 1) | launch script | yes |
| `OTEL_RESOURCE_ATTRIBUTES` | `service.version`, `deployment.environment.name`, … (step 2) | launch env (values may vary per env) | yes (keys) |
| `OTEL_SEMCONV_STABILITY_OPT_IN` | `http,database` — emit current semconv (step 1) | launch script | yes |

- Set what you can in committed launch config (start script, Dockerfile, etc.) and say what you set and where.
- For anything the operator must set (especially secrets), print a copy-pasteable block:

  ```
  # Add to your launch environment before running:
  export OTEL_EXPORTER_OTLP_ENDPOINT=https://api.honeycomb.io
  # optional: auth for the endpoint; omit for an internal collector. Keep in secrets, not git.
  export OTEL_EXPORTER_OTLP_HEADERS="x-honeycomb-team=$HONEYCOMB_KEY"
  # To use the latest semantic naming conventions where possible.
  export OTEL_SEMCONV_STABILITY_OPT_IN=http,database
  ```

## Fixing verifier findings

If verification handed you findings, fix **exactly those** against the existing instrumentation, then
re-verify — don't re-run the whole flow. The findings in your task are all the context you have (you're
a fresh instrumenter; you can't see the verifier's session), so act on them directly. Map each to its
remedy:

| Finding | What it means | Fix |
|---|---|---|
| `missing_attribute` — a **standard** semconv name (`http.request.method`, `db.query.text`, `server.address`, …) "does not exist in the registry" | dependency declared but not imported | add the `imports: { attribute_groups: [registry.*] }` block to a group file (step 3) |
| `missing_attribute` — a **library/runtime** attribute your code doesn't set (`asgi.event.type`, framework attrs) | registry missing a passed-through attribute | declare it in `weaver/libraries.yaml` (step 3) |
| `missing_attribute` — one of your **own** `app.*` attributes | you emit it but didn't declare it | add it to your `weaver/app.yaml` group |
| `violation` — a custom attribute under a standard namespace (`db.rows_affected` under `db.*`) | collides with imported semconv | rename to `app.*`, or reuse the standard attribute (`db.response.returned_rows`) |
| Legacy attribute names present (`http.method`, `db.statement`, `net.peer.ip`) — from the span review, not weaver | semconv opt-in didn't take effect, or instrumentation is stale | set `OTEL_SEMCONV_STABILITY_OPT_IN=http,database` and upgrade instrumentation to latest (step 1) |
| Orphan / disconnected spans | broken context propagation | ensure context flows across the boundary (async hop, manual parenting) |
| `improvement` / `not_stable` advice | stability level on your own attributes | **not a failure — no action** |
| `total_entities: 0` (weaver saw nothing) | telemetry never reached weaver | not a registry problem — fix traffic/exporter, then re-verify |

After fixing, re-run verification — the instrumentation isn't done until it returns PASS.
