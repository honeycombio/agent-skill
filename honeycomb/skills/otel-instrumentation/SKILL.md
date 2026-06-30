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
  version: "0.2.0"
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

### 6. Prove it works

Drive the app under real, representative traffic so it emits telemetry. **Run it with the export
configuration actually active** — the correct `OTEL_*` environment variables in place
(`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS` carrying the `x-honeycomb-team` key, and
`OTEL_SERVICE_NAME`) — otherwise nothing reaches the destination and there is nothing to judge. Then
**hand off to the `otel-verification` skill to judge it.** Verification reads the emitted telemetry (in Honeycomb and
against the standards) and reports the gaps — it does not generate traffic of its own. Fix what it
flags, re-run the traffic, and repeat until it is clean. The work isn't done until the telemetry is
verified, not merely emitted.

### 7. Hand back

Lead with the outcome, not a diff: tell the user, in plain language, **what they can now see and
ask** that they couldn't before — tied to the things they said matter — and point them at the live
data in Honeycomb as proof. Briefly summarise **what changed** in their code so they know what
landed. Finally, leave them able to **re-verify anytime**: the `otel-verification` skill needs only
query access to this environment — no rerun of the app — so they can re-check after future changes.
