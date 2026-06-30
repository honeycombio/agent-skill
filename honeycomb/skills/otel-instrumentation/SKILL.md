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
context needed to debug it in production, and arrive in Honeycomb — **proven under real traffic
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
- **what the app does and what the user cares about debugging** — ask; this drives the business context
- **attribute standards** — ask whether the org has a registry or document that *defines existing attributes and their values* (a **weaver registry**, or an established conventions page) to look up and reuse verbatim — alongside the OpenTelemetry semantic conventions
- **naming conventions** — ask the rules for *creating a new* attribute when no standard one fits (namespace/prefix, casing, structure); default to an `app.*` namespace if there are none
- **focus** — optionally a specific area to prioritise; otherwise cover the app broadly

## Steps

### 1. Gather

Read the repo to establish the language, frameworks, entry points, and how it builds and runs.
Confirm the service name with the user. **When exporting directly to Honeycomb, derive the
environment from the ingestion key** rather than asking: call `GET /1/auth` against the chosen
region with the key in the `x-honeycomb-team` header and read `environment.name`; confirm it with
the user (a Classic key returns an empty name). When the endpoint is a collector/gateway instead,
there is no environment to derive — telemetry lands wherever that endpoint forwards it. Then ask
what matters: the domain entities, decisions, and operations they would want to slice by when
something is wrong. Capture a short list — it is the input for step 4.

### 2. Enable auto-instrumentation

Get the app emitting **traces, metrics, and logs** out of the box. Where the language offers a
zero-code auto-instrumentation agent (e.g. Java, Python, Node, .NET), prefer it; otherwise wire up
the OpenTelemetry SDK with the standard framework instrumentations. Keep custom code to a minimum —
take the least-custom path the language and framework support. Set the service identity —
`service.name`, plus `service.version` where readily available. This is one knob, not two: prefer the
`OTEL_SERVICE_NAME` environment variable (the default path, and the only one for zero-code agents)
over setting it in code, and apply it consistently with step 6.

**Declare the new dependencies in the project's manifest, not just the live environment.** Add the
OpenTelemetry packages the way the project declares its other dependencies (`uv add` / `pyproject.toml`,
`go get`, `package.json`, `pom.xml`) and update the lockfile, so a clean checkout running the project's
canonical install reproduces the instrumented dependency set. If the manifest install fails because the
new packages conflict with an existing dependency, resolve the conflict — adjust a pin, scope the
conflicting package to an optional group you exclude, or pick compatible versions.

To make sure that libraries are updated to their latest version and that if needed `OTEL_SEMCONV_STABILITY_OPT_IN` is set with the appropriate values for the libraries involved so that the latest version of the semantic conventions are used.

### 3. Send telemetry to Honeycomb

Configure OTLP export to the chosen endpoint through environment/config — **never hardcode
credentials.** Going directly to Honeycomb, that is `https://api.honeycomb.io` (US) or
`https://api.eu1.honeycomb.io` (EU), authenticated with the ingestion key in the `x-honeycomb-team`
header; going to an organisation's collector/gateway, use that URL and whatever auth it expects.
Cover all three signals. Then **confirm data is actually arriving**: run the app, drive a little
traffic, and check the telemetry lands at the destination (query Honeycomb, or the MCP) before going
further — do not build on an unverified pipeline.

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

Write the attributes down so the conventions stay consistent and can be checked mechanically. **First
look for an existing weaver registry in the repo** — a `registry_manifest.yaml` (or a `manifest.yaml`
alongside attribute-group files) — and honour the `app_weaver_registry` / `import_registries` you were
given at intake. **If one exists, extend it** rather than starting over. Otherwise create a small
registry of your own that documents the custom attributes you introduced in step 4 (name, type, a
one-line brief, example values), importing the upstream OpenTelemetry semantic conventions so the
standard attributes you reused resolve too.

Validate the registry **statically** with `weaver registry check` and fix whatever it flags — a
malformed or inconsistent registry is a defect to correct now. This is a static check of the registry
*definition* itself; you do not run live telemetry through weaver here — proving the emitted telemetry
is correct happens next.

The manifest's identity fields — `name`, and either `schema_url` or both `schema_base_url` and
`semconv_version` — live at the **top level** of the document, with imported registries in a top-level
list. A minimal valid shape:

```yaml
name: <service>-registry
schema_url: https://opentelemetry.io/schemas/<semconv-version>
registries:
  - url: https://github.com/open-telemetry/semantic-conventions.git[model]
    name: semconv
```

### 6. Prove it works

Drive the app under real, representative traffic so it emits telemetry. **Run it with the export
configuration actually active** — the correct `OTEL_*` environment variables in place
(such as `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS` carrying the `x-honeycomb-team` key, and
`OTEL_SERVICE_NAME` and `OTEL_SEMCONV_STABILITY_OPT_IN` if needed.) — otherwise nothing reaches the destination and there is nothing to judge. Finish all instrumentation tasks before starting the application and then **hand off to the `otel-verification` skill to judge it.** Verification reads the emitted telemetry (in Honeycomb and
against the standards) and reports the gaps — it does not generate traffic of its own. Fix what it
flags, re-run the traffic, and repeat until it is clean. The work isn't done until the telemetry is
verified, not merely emitted.

**Keep the run loop tight** — booting and driving the app is usually the slowest thing you do, so
don't repeat it needlessly. So finish all instrumentation Start the app **once** and keep it running across the verify→fix→re-verify
cycle; only restart when you've changed something the running process loaded at startup (app code, or
the `OTEL_*` export/SDK config). Wait for readiness with a **bounded poll** — loop on a concrete signal
(a startup log line, a health endpoint, the port accepting connections) with a timeout, and bail early
if the process has exited — rather than a foreground `tail -f` (which can block long past the match) or
a fixed `sleep` guess. Likewise, before you read telemetry back, wait for the exporter to actually
flush — watch for its own confirmation, or use a single bounded wait sized to the batch interval — not
a blind sleep.

**Separate runtime failures from instrumentation defects.** Your job is the telemetry, not the app's
own runtime. If the app fails in a way unrelated to your changes — won't start, datastore in a bad
state, a port taken, app-level errors you didn't introduce — that's an environment failure, not an
instrumentation defect. Capture the evidence and hand back rather than trying to fix the app.

### 7. Hand back

Lead with the outcome, not a diff: tell the user, in plain language, **what they can now see and
ask** that they couldn't before — tied to the things they said matter — and point them at the live
data in Honeycomb as proof. Briefly summarise **what changed** in their code so they know what
landed. Finally, leave them able to **re-verify anytime**: the `otel-verification` skill needs only
query access to this environment — no rerun of the app — so they can re-check after future changes.

Finally, end with a list of environment variables that the user should set to send telemetry to an endpoint. At a minimum, this would include `OTEL_EXPORTER_OTLP_ENDPOINT` with optionally `OTEL_EXPORTER_OTLP_HEADERS` to do any authentication. If headers like `OTEL_SEMCONV_STABILITY_OPT_IN` and `OTEL_SERVICE_NAME` are not already set in startup scripts, they need to be mentioned as well.
