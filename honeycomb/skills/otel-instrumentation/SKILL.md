---
name: otel-instrumentation
description: >
  Make an application observable: add OpenTelemetry instrumentation so the app emits traces,
  metrics, and logs that make it debuggable in production, send them to Honeycomb, and prove
  it works.
  Trigger phrases: "instrument my app", "add tracing",
  "set up OpenTelemetry", "configure OTel", "add custom spans",
  "add attributes to spans", "send traces to Honeycomb",
  "set up OTLP", "add span events",
  "add span links", "set up tracing for [any language]",
  "configure the OTel Collector",
  or any request about OpenTelemetry SDK setup, custom instrumentation,
  or sending data to Honeycomb.
metadata:
  version: "0.2.1"
---

# OpenTelemetry Instrumentation

Make the target application observable: run the way it normally runs, it should emit traces,
metrics, and logs that follow current OpenTelemetry semantic conventions, carry the business
context needed to debug it in production — Make sure it is **proven under real traffic
before you call it done.**

## Before you start

Establish the following before changing code. Some arrive with your task; discover the rest from the
repo. **Collect everything you still need into a single batch of questions, put them to the user up
front, and confirm a short plan — then implement.** Don't drip-feed questions mid-implementation,
and don't guess at anything only the user knows.

- **repo path** — the app to instrument
- **service name** — the `service.name` / Honeycomb dataset the telemetry uses (ask if not given; never invent one)
- **language + runtime**, and the **frameworks** in play (HTTP server, DB client, ORM, queue) — discover from the repo
- **how to build, run, and drive real traffic** through the app — discover or ask
- **OTLP endpoint** — where telemetry is sent. If not provided, ask whether it is **Honeycomb (US)**, **Honeycomb (EU)**, or **Other** (an organisation's collector / gateway — the user supplies the URL)
- **Honeycomb ingestion key** — the API key to send with *when exporting directly to Honeycomb* (ask; never hardcode it). The environment it sends to is *derived from the key* — see step 1. When the endpoint is a collector/gateway, use whatever auth that endpoint expects (often none from the app)
- **query access for verification** — the Honeycomb MCP, or a Honeycomb *query* API key (read access) for the destination environment. Distinct from the ingestion key above; step 6 needs it so verification can read back what landed
- **what the app does and what the user cares about debugging** — this drives the business context
- **attribute standards** — ask whether the org has a registry or document that *defines existing attributes and their values* (a **weaver registry**, or an established conventions page) to look up and reuse verbatim — alongside the OpenTelemetry semantic conventions
- **naming conventions** — ask the rules for *creating a new* attribute when no standard one fits (namespace/prefix, casing, structure); default to an `app.*` namespace if there are none
- **focus** — optionally a specific area to prioritise; otherwise cover the app broadly

## Steps

### 1. Gather

Read the repo to establish the language, frameworks, entry points, and how it builds and runs.
Confirm the service name with the user. If the OTLP endpoint is a Honeycomb API endpoint, derive the
environment from the ingestion key** rather than asking: call `GET /1/auth` against the chosen
region with the key in the `x-honeycomb-team` header and read `environment.name`; confirm it with
the user (a Classic key returns an empty name).
And if the OTLP endpoint is a Honeycomb API endpoint, make sure to also set OTEL_EXPORTER_OTLP_HEADERS to `x-honeycomb-team=` with the ingest key.

### 2. Enable auto-instrumentation

Get the app emitting **all three signals — traces, metrics, and logs** — out of the box. Where the
language offers a
zero-code auto-instrumentation agent (e.g. Java, Python, Node, .NET), prefer it; otherwise wire up
the OpenTelemetry SDK with the standard framework instrumentations. Keep custom code to a minimum —
take the least-custom path the language and framework support. Set the service identity —
`service.name`, plus `service.version` where readily available. This is one knob, not two: prefer the
`OTEL_SERVICE_NAME` environment variable (the default path, and the only one for zero-code agents)
over setting it in code, and apply it consistently with step 7.

**A signal only counts if it is actually exported — wire each pipeline end to end.** A zero-code agent
normally covers all three; an SDK setup must wire each one explicitly, and it is easy to build a
pipeline that emits nothing. **Logs** are the usual casualty, because a working log pipeline is a full
chain: *the logger the app already uses* → an OTel bridge/handler → a `LoggerProvider` → an OTLP log
exporter. Two half-configurations look done but export zero records: enabling only log/trace
**correlation** (injecting trace IDs into log lines) with no export pipeline; or standing up a
`LoggerProvider` + exporter but never **bridging** the app's real logger to it, so it keeps writing to
stdout. **Metrics** have the same shape — a `MeterProvider` with an OTLP metric exporter, not just
instruments. Don't assume; step 6 must confirm records of each signal actually arrive.

**Declare the new dependencies in the project's manifest, not just the live environment.** Add the
OpenTelemetry packages the way the project declares its other dependencies (`uv add` / `pyproject.toml`,
`go get`, `package.json`, `pom.xml`) and update the lockfile, so a clean checkout running the project's
canonical install reproduces the instrumented dependency set. If the manifest install fails because the
new packages conflict with an existing dependency, resolve the conflict — adjust a pin, scope the
conflicting package to an optional group you exclude, or pick compatible versions.

Lastly, make sure that all Open Telemetry libraries are updated to the latest version and that they support the latest semantic conventions. Some libraries require a particular value to be set in the `OTEL_SEMCONV_STABILITY_OPT_IN` environment variable. If that is the case, make sure that value is added to the environment variable and the environment variable is added to any startup scripts and communicated at the report at the end.

If the latest version of a particular library does not support the latest semantic conventions, it is ok to ignore the warnings from the verification step for this particular subsystem, as long as this is explicitely mentioned at the end of the run.

**Only make instrumentation changes in the application's own source code — never in its dependencies.**
Code that comes from an installed package or framework (anything you can't edit in the repo's own
sources) is covered by auto-instrumentation at runtime; you can't ship edits to it, and reading or
decompiling it to instrument it is wasted effort. Add custom spans and business attributes only in the
app's own code and its extension points (handlers, services, middleware/filters/interceptors), and let
auto-instrumentation handle everything that lives in a dependency.

### 3. Look up standards

**First look for an existing weaver registry in the repo** — a `registry_manifest.yaml` (or a `manifest.yaml`
alongside attribute-group files) — and make sure the `app_weaver_registry` / `import_registries` you were
given at intake are included. **If one exists, extend it** rather than starting over. Otherwise create a small
registry of your own.

Put the registry in its **own subdirectory** (e.g. `telemetry/registry/`), **never the repo root** —
weaver treats the whole registry directory as the registry and chokes on any non-registry YAML it
finds there (a collector config, a linter config, …), which makes the live-check fail to start
entirely. Name the manifest `manifest.yaml`. Its identity fields — `name`, and either `schema_url` or
both `schema_base_url` and `semconv_version` — live at the **top level**, with imported registries
declared in a top-level **`dependencies:`** list (each entry a `name` and a `registry_path`). A
minimal valid shape:

```yaml
name: <service>-registry
# Use your OWN schema_url host — NOT opentelemetry.io/schemas/... A schema_url under
# opentelemetry.io makes your registry share the upstream's identity and weaver fails with a
# "circular dependency" error.
schema_url: https://<your-app>/schemas/1.0.0
dependencies:
  - name: otel
    registry_path: https://github.com/open-telemetry/semantic-conventions.git[model]
```

`dependencies:` makes the upstream conventions *resolvable*, but importing alone does **not** make
them count in live-check — the check only credits attributes your registry actually **references**, so
standard attributes are still flagged as undefined. Reference the namespaces you emit with a top-level
**`imports:`** block (a sibling of `groups:`, in any registry file). `imports:` pulls in **signals** —
`spans`, `metrics`, `events`, `entities` — by glob, and each imported signal transitively references
its attributes:

```yaml
imports:
  spans:
    - http.*
    - db.*
  metrics:
    - http.*
    - db.*
```

Import the signal namespaces your telemetry actually uses (add `messaging.*`, `rpc.*`, etc. as they
apply). `imports:` only takes signal types — there is no bare `attributes:` import — so a few
attributes in signal-less namespaces will still be flagged; pick those up reactively with explicit
refs in step 5. A `registries:` block (or any other spelling) is **silently ignored** and
`weaver registry check` still passes, so a wrong import only surfaces at live-check. After writing the
manifest, confirm with **`weaver registry live-check`** that standard attributes such as `http.route`
validate rather than being reported as undefined.

If given a URL with standards that is not a valid weaver registry, read the page and extract all attributes and any format is given and re-use those whenever possible in step 5.


### 4. Add business context

Guided by the **focus** from intake where one was given (otherwise across the app), attach what the
user said matters to the telemetry — favouring **wide events**: put
many attributes on a single span rather than spreading them thin, and don't shy away from
**high-cardinality** values (user, tenant, order, request IDs), which are what make the data
debuggable in Honeycomb. Add them on the spans where that information is already available, so the
user can group and filter by it. Add new spans only where a real unit of work isn't already captured
by auto-instrumentation — prefer enriching existing spans over creating new ones.

**Reuse what's already defined before inventing anything.** Look the standards up rather than
guessing — the org's attribute registry or conventions document from intake, and the OpenTelemetry
semantic conventions (<https://opentelemetry.io/docs/specs/semconv/>), via the Honeycomb MCP's
semantic-convention lookup (`search_semconv`, `get_semconv_attribute`) when available. Where an
attribute is already defined, **use its exact name and match the value shape it expects.** Only when
nothing standard fits do you mint a new attribute — and then follow the **naming conventions**
(namespace, casing, structure) from intake, defaulting to the `app.*` namespace. Don't apply names
from a generic checklist.

### 5. Define your attributes in a weaver registry

Define all attributes that you have added in step 4, except for ones already defined in an imported registry. Include name, type, a
one-line brief and example values.

The `imports:` block from step 3 covers the standard attributes carried by the signals you import. For
any **standard** attribute the live-check still flags as undefined — the stragglers that live in
signal-less namespaces (e.g. `url.*`, `client.*`, `user_agent.*`) — add an explicit `ref:` to it in a
group so it validates too. Let the live-check tell you which ones rather than enumerating them up
front.

Validate the registry **statically** with `weaver registry check` and fix whatever it flags — a
malformed or inconsistent registry is a defect to correct now. This is a static check of the registry
*definition* itself;

### 6. Prove it works

Once you have finished all of the instrumentation changes that are needed, drive the app under real, representative traffic so it emits telemetry via the generate traffic cmd. **Run it with the export
configuration actually active** — the correct `OTEL_*` environment variables in place that you gathered in step 1.
(such as `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`,
`OTEL_SERVICE_NAME` and `OTEL_SEMCONV_STABILITY_OPT_IN` if needed.) — otherwise nothing reaches the destination and there is nothing to judge.

**Confirm all three signals actually arrived** — query the destination for traces **and** metrics
**and** logs under your `service.name`. A signal with zero records means its export pipeline is
broken (see step 2), not that the app is quiet — treat it as a defect to fix, not a pass. Do this
before handing off so a half-wired metrics or logs pipeline can't slip through as "done".

**Then spawn a Task sub-agent to verify the output with the `otel-verification` skill.**
In the prompt, include the information needed to find telemetry. What service.name, environment, weaver registry and naming conventions that you were given.

If the check comes back a FAIL, fix what it flagged, start the application again, generate traffic and call the verification skill one more time in a fresh Task sub-agent with the same prompt.

If the second check also fails, make sure to mention that in the final output to the user with an overview of the failures.

**Keep the verify loop tight** — booting and driving the app is usually the slowest thing you do, so
don't repeat it needlessly.
Wait for readiness with a **bounded poll** — loop on a concrete signal
(a startup log line, a health endpoint, the port accepting connections) with a timeout, and bail early if the process has exited — rather than a foreground `tail -f` (which can block long past the match) or a fixed `sleep` guess. Likewise, before you read telemetry back, wait for the exporter to actually flush — watch for its own confirmation, or use a single bounded wait sized to the batch interval — not a blind sleep.

**Separate runtime failures from instrumentation defects.** Your job is the telemetry, not the app's
own runtime. If the app fails in a way unrelated to your changes — won't start, datastore in a bad
state, a port taken, app-level errors you didn't introduce — that's an environment failure, not an
instrumentation defect. Capture the evidence and hand back rather than trying to fix the app.

### 7. Hand back

Lead with the outcome, not a diff: tell the user, in plain language, **what they can now see and
ask** that they couldn't before — tied to the things they said matter — and point them at the live
data in Honeycomb as proof. Briefly summarise **what changed** in their code so they know what landed.

Include some of the evidence from the last verification step so the user can explore their new telemetry.

Finally, end with a list of environment variables that the user should set to send telemetry to an endpoint. At a minimum, this would include `OTEL_EXPORTER_OTLP_ENDPOINT` with optionally `OTEL_EXPORTER_OTLP_HEADERS` to do any authentication. If headers like `OTEL_SEMCONV_STABILITY_OPT_IN` and `OTEL_SERVICE_NAME` are needed and not set in existing startup scripts, they need to be mentioned as well.
