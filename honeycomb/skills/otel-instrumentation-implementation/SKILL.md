---
name: otel-instrumentation-implementation
description: >
  Implementation playbook for APPLYING OpenTelemetry instrumentation to an application — the
  concrete steps: enable auto-instrumentation across all three signals (traces, metrics, and
  logs) and opt into stable semantic conventions, add service.version, create a weaver registry,
  add business-context instrumentation, and set/communicate the required environment-variable
  contract. This is the "how to actually write the instrumentation"
  reference, used by the instrumenter role. For running a full engagement (coordinating
  implementation with independent verification), use the `otel-instrumentation` skill instead.
metadata:
  version: "1.3.1"
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

**First, read the config guide for your language** — `references/<language>.md` (`go.md`, `python.md`,
`java.md`, …) next to this skill. The steps below are general; that file has the stack-specific way to
apply them reliably (exporter selection, `service.name`, init order, dependencies) and the traps that
otherwise **silently drop telemetry or mis-route it** (e.g. a hardcoded gRPC exporter, or a
`service.name` set only in a launch wrapper the deployer doesn't use).

**Select the exporter from `OTEL_EXPORTER_OTLP_PROTOCOL` — never hardcode the transport.** An exporter
pinned to one transport (`grpc` vs `http/protobuf`) while the endpoint speaks the other silently drops
**all** telemetry, with no error — and it's invisible to console-based checks, which bypass the OTLP
path. Your language file shows how to honor the env var without hardcoding it.

**Emit all three signals — traces, metrics, and logs**, not just tracing. Wire the metric reader and
the log bridge (and the metric/log contrib packages), not only the tracer, and keep the per-signal
exporters at `otlp` (never `none`). Your language file has the exact wiring — agent defaults vs.
manual providers. Verify after first traffic that spans, metric datapoints, **and** log records all
appear.

**Upgrade all OpenTelemetry dependencies to their latest releases** — SDK, exporters, every
auto-instrumentation/contrib package, and any language agent. Stale versions emit legacy semconv
names and miss options — a common cause of missing or wrong-named telemetry. Rebuild and confirm
the app still runs.

**Always set `service.name`** — Honeycomb names the dataset from it; never leave it at the
`unknown_service` default. Set it via `OTEL_SERVICE_NAME` in the launch script (applied every start),
and derive it deterministically: the artifact/module name from the build config (`pom.xml`,
`package.json`, `pyproject.toml`, `go.mod`, …), else the repo/directory name. For a compiled binary,
set it as a **code default** on the resource too — not only the launch env, which the operator may not
use (see your language file). (Per-environment resource attributes — step 2 — still come from
`OTEL_RESOURCE_ATTRIBUTES`.)

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

**Account for attributes your code doesn't set — in `weaver/libraries.yaml`.** Verification treats
**any** undeclared attribute as a FAIL, including ones a library or the runtime emits (e.g. what the
HTTP/ASGI/servlet layer adds to spans). Standard semconv attrs are already covered by the `imports`
block; declare the rest — library/framework attributes not in semconv — in a **separate**
`weaver/libraries.yaml` group, kept apart from your `app.*` attributes so authorship is clear:

```yaml
# weaver/libraries.yaml — attributes a library/runtime emits (NOT set by app code). Only
# library-specific ones; semconv attributes are already covered by the imports block.
groups:
  - id: registry.libraries
    type: attribute_group
    brief: Attributes emitted by instrumentation libraries / runtime, not set by app code
    attributes:
      # One entry per attribute the live-check flags as missing. Use the EXACT name from
      # the report — don't guess attribute names ahead of time; you can't know which
      # library/runtime attributes a given stack emits until you see them in the telemetry.
      - id: <library>.<attribute>
        type: string
        brief: <what this library/runtime attribute represents>
        stability: development
        examples: ["<observed value>"]
```

You populate this **reactively**, never speculatively — declare an attribute here only after the
live-check reports it missing (see **Fixing verifier findings** below).

**Declare the metrics you emit, not just attributes.** The registry describes *all* the
telemetry the app emits, and you are emitting metrics now (step 1) — so the live-check flags
any emitted metric that isn't in the registry as a `missing_metric` violation, just like an
undeclared attribute. Declare each metric the live-check reports as missing as its own
`type: metric` group. Custom business metrics (the counters/histograms from step 4) go under
your `app.*` namespace:

```yaml
groups:
  - id: metric.app.orders.placed
    type: metric
    metric_name: app.orders.placed
    brief: Count of orders placed
    instrument: counter
    unit: "{order}"
    stability: development
```

For a **standard** semconv metric emitted by auto-instrumentation
(`http.server.request.duration`, `jvm.memory.used`, …) that the live-check flags, declare it the
same way, using its exact semconv `metric_name`, `instrument`, and `unit`. As with the
library attributes above, populate these **reactively** — declare a metric only once the
live-check reports it missing, not speculatively.

Reference the registry-defined attribute names from your instrumentation (ideally via
generated constants) instead of hardcoding attribute-name strings, so the business
instrumentation in step 4 stays consistent and reviewable.

## 3b. Verify the registry resolves — do not skip

`weaver registry check` confirms the files are well-formed, but it does **not** catch a missing or
misplaced `imports` block — the single most common and most damaging registry defect. Without that
block the dependency merges nothing, so the live-check flags *every* standard attribute your
telemetry emits (hundreds to tens of thousands of `missing_attribute` violations). Catch it
deterministically, with no telemetry needed, by confirming an upstream semconv attribute actually
resolves **into** your registry:

```bash
# point -r at your registry dir (the one holding manifest.yaml)
weaver registry resolve -r weaver --format json \
  | grep -q 'http.request.method' && echo 'imports OK' \
  || echo 'IMPORTS MISSING — the imports block is absent or not taking effect'
```

If this prints `IMPORTS MISSING`, fix the `imports` block before continuing — passing
`weaver registry check` is **not** evidence the import worked.

## 4. Add business context instrumentation

Auto-instrumentation captures the plumbing; this step captures the domain. Add
attributes for the entities and decisions that matter when debugging — user/
tenant IDs, order/cart IDs, feature flags, result counts, branch taken — onto
the active span, using the registry-defined names from step 3. Create custom
spans only for meaningful units of work not already covered by
auto-instrumentation, and record exceptions and outcomes so failures are
queryable.

The same domain context belongs in the other two signals where it adds value:
record domain **metrics** for business-meaningful counts and durations the
auto-instrumentation doesn't already cover (e.g. orders placed, items per cart,
queue depth) via instruments on a `Meter`, and ensure the app's **logs** flow
through the OTel logging bridge so log records are correlated to the active trace.
Reuse the registry-defined names across all three signals.

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
| `OTEL_TRACES_EXPORTER` / `OTEL_METRICS_EXPORTER` / `OTEL_LOGS_EXPORTER` | keep all three at `otlp` so every signal is exported — never `none` (step 1) | launch script | yes |

- Set what you can in committed launch config (start script, Dockerfile, etc.) and say what you set and where.
- For what the operator must supply (especially the secret), print a copy-pasteable block:

  ```
  # Add to your launch environment before running:
  export OTEL_EXPORTER_OTLP_ENDPOINT=https://api.honeycomb.io
  export OTEL_EXPORTER_OTLP_HEADERS="x-honeycomb-team=$HONEYCOMB_KEY"   # secret — keep out of git
  export OTEL_SEMCONV_STABILITY_OPT_IN=http,database
  ```
  (The `OTEL_*_EXPORTER` vars default to `otlp`; set them explicitly only if something might override them.)

## Fixing verifier findings

If verification handed you findings, fix **exactly those** against the existing instrumentation, then
re-verify — don't re-run the whole flow. The findings in your task are all the context you have (you're
a fresh instrumenter; you can't see the verifier's session), so act on them directly. Map each to its
remedy:

| Finding | What it means | Fix |
|---|---|---|
| `missing_attribute` — a **standard** semconv name (`http.request.method`, `db.query.text`, `server.address`, …) "does not exist in the registry" | dependency declared but not imported | add the `imports: { attribute_groups: [registry.*] }` block to a group file (step 3) |
| `missing_attribute` — a **library/runtime** attribute your code doesn't set (something from the HTTP/ASGI/servlet or process layer) | registry missing a passed-through attribute | declare it (by its exact reported name) in `weaver/libraries.yaml` (step 3) |
| `missing_attribute` — one of your **own** `app.*` attributes | you emit it but didn't declare it | add it to your `weaver/app.yaml` group |
| `missing_metric` — an emitted metric "does not exist in the registry" | metrics are emitted but not declared in the registry | declare the flagged metric (by its exact name) as a `type: metric` group — custom metrics under `app.*`, standard semconv metrics by their published name (step 3) |
| `violation` — a custom attribute under a standard namespace (`db.rows_affected` under `db.*`) | collides with imported semconv | rename to `app.*`, or reuse the standard attribute (`db.response.returned_rows`) |
| Legacy attribute names present (`http.method`, `db.statement`, `net.peer.ip`) — from the span review, not weaver | semconv opt-in didn't take effect, or instrumentation is stale | set `OTEL_SEMCONV_STABILITY_OPT_IN=http,database` and upgrade instrumentation to latest (step 1) |
| Orphan / disconnected spans | broken context propagation | ensure context flows across the boundary (async hop, manual parenting) |
| No metric datapoints received | metrics signal not exported | enable metric auto-instrumentation / a `MeterProvider` + OTLP metric exporter; ensure `OTEL_METRICS_EXPORTER` isn't `none` (step 1) |
| No log records received | logs signal not bridged/exported | wire the logging bridge into a `LoggerProvider` + OTLP log exporter; ensure `OTEL_LOGS_EXPORTER` isn't `none` (step 1) |
| `improvement` / `not_stable` advice | stability level on your own attributes | **not a failure — no action** |
| `total_entities: 0` (weaver saw nothing) | telemetry never reached weaver | not a registry problem — fix traffic/exporter, then re-verify |

After fixing, re-run verification — the instrumentation isn't done until it returns PASS.
