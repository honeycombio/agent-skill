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

Make the target application observable: running the way it normally runs, it should emit traces,
metrics, and logs that follow current OpenTelemetry semantic conventions and carry the business
context needed to debug it in production. **Prove it under real traffic before you call it done.**

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
environment from the ingestion key rather than asking: call `GET /1/auth` against the chosen region
with the key in the `x-honeycomb-team` header and read `environment.name`; confirm it with the user
(a Classic key returns an empty name). For that endpoint, also set `OTEL_EXPORTER_OTLP_HEADERS` to
`x-honeycomb-team=<ingest key>`.

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

Lastly, check whether the OpenTelemetry libraries in use support the current semantic conventions.
Where a library's installed version is behind — it emits deprecated attributes and a newer version
would emit the current ones — **ask the user whether they want to upgrade it (unless you already
have explicit permission), and upgrade only if they agree.** Some libraries also require a specific
value in the `OTEL_SEMCONV_STABILITY_OPT_IN` environment variable. When that applies, set that
variable, add it to any startup scripts, and note it in the final report.

A library whose **latest** version still emits deprecated conventions — and that no
`OTEL_SEMCONV_STABILITY_OPT_IN` value or configuration can move onto the current ones — is a **known
limitation, not a defect you can fix**: you can't ship changes to a dependency (see below). Don't
conclude this until you've actually exhausted the upgrade *and* the opt-in — it is not a shortcut
past a fixable gap. Once you have, note which library it is and which attributes or namespace it
emits the old way, and carry that forward: verification will flag it in step 6, where you reconcile
it rather than chase it, and you disclose it in step 7.

**Only make instrumentation changes in the application's own source code — never in its dependencies.**
Code that comes from an installed package or framework (anything you can't edit in the repo's own
sources) is covered by auto-instrumentation at runtime; you can't ship edits to it, and reading or
decompiling it to instrument it is wasted effort. Add custom spans and business attributes only in the
app's own code and its extension points (handlers, services, middleware/filters/interceptors), and let
auto-instrumentation handle everything that lives in a dependency.

### 3. Look up standards

Your telemetry gets judged against a **weaver registry** — a truthful manifest of every attribute
you emit, standard and custom. **First look for an existing registry in the repo** — a
`registry_manifest.yaml` (or a `manifest.yaml` alongside attribute-group files) — and make sure the
`app_weaver_registry` / `import_registries` you were given at intake are included. **If one exists,
extend it** rather than starting over. Otherwise create a small registry of your own.

Get the upstream OpenTelemetry conventions resolvable as a dependency and reference the standard
namespaces you actually emit, so the registry is a truthful manifest of your telemetry. The exact
YAML shape, directory rules, and import spelling — including the trap where a misspelled import is
silently ignored while `weaver registry check` still passes — are in
**[references/weaver-registry.md](references/weaver-registry.md)**.

If given a URL with standards that is not a valid weaver registry, read the page, extract the
attributes and any formats it defines, and reuse those in step 5.


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

**This discipline covers every attribute you set yourself — including the resource attributes you
configure during setup** (via `OTEL_RESOURCE_ATTRIBUTES` or the SDK's `Resource`), not just the
business attributes you add in code. Standard conventions get renamed as they stabilise, and setup
guides often carry the old spelling; a self-set attribute using a deprecated name (for example
`deployment.environment`, superseded by `deployment.environment.name`) is a defect you own and must
correct — look up the current spelling rather than copying an older example. This is unlike a
deprecated attribute emitted by a library you can't edit, which is a known limitation; anything you
write yourself, you can and must get right.

### 5. Define your attributes in a weaver registry

Add a definition for every attribute you introduced in step 4 that isn't already covered by an
import — name, type, a one-line brief, and example values. The registry is a truthful manifest of
**everything your telemetry emits**, not just the attributes you wrote by hand — the
auto-instrumentation libraries you enabled add their own, and each one still needs a home in the
registry. Walk the attributes your instrumentation actually emits and make sure each one is
accounted for:

- **standard attributes** are imported (or, for signal-less namespaces like `url.*`, `client.*`,
  `user_agent.*`, explicitly `ref:`'d — the `imports:` block from step 3 can't pull them in);
- **non-standard attributes a library emits** (e.g. framework/middleware passthrough keys that
  aren't part of any semantic convention) aren't importable or ref'able, so define them yourself
  just as you would your own — a name, type, and one-line brief. They are part of your telemetry; a
  truthful manifest documents them too.

See **[references/weaver-registry.md](references/weaver-registry.md)** for the mechanics.

Validate the registry **statically** with `weaver registry check` and fix whatever it flags — a
malformed or inconsistent registry is a defect to correct now. This checks the registry *definition*
itself; proving it matches the emitted telemetry happens in step 6.

### 6. Prove it works

Once you have finished all of the instrumentation changes that are needed, drive the app under real,
representative traffic so it emits telemetry. **Run it with the export configuration actually active** — the correct `OTEL_*` environment variables in place that you gathered in step 1.
(such as `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`,
`OTEL_SERVICE_NAME` and `OTEL_SEMCONV_STABILITY_OPT_IN` if needed.) — otherwise nothing reaches the destination and there is nothing to judge.

**Confirm all three signals actually arrived** — query the destination for traces **and** metrics
**and** logs under your `service.name`. A signal with zero records means its export pipeline is
broken (see step 2), not that the app is quiet — treat it as a defect to fix, not a pass. Do this
before handing off so a half-wired metrics or logs pipeline can't slip through as "done".

**Then invoke the `otel-verification` skill to verify the output** — run it with a clean context (a
sub-agent / separate task) so it judges the telemetry independently. Give it the information needed
to find the telemetry: the `service.name`, environment, weaver registry, and naming conventions you
were given.

The verification skill judges independently and doesn't know which gaps you already found unfixable,
so **reconcile its findings against what you learned in step 2 before you act.** A flagged convention
that you've confirmed comes from an un-upgradable library is *expected*: carry it to step 7, don't
try to fix it, and — since rebooting and re-driving the app is the slowest thing you do — never
re-run the app for it. If verification flags a deprecated convention you hadn't already identified,
check then whether the latest library version or the opt-in can fix it; if neither can, it's a known
limitation too, and the same applies.

Fix every *other* flagged finding, then start the application again, generate traffic, and run the
verification skill once more with a fresh context and the same prompt.

If the second check still fails on findings that are **not** known library limitations, mention that
in the final output to the user with an overview of the failures.

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

**Call out any known limitations explicitly.** For each subsystem where an un-upgradable library
still emits deprecated conventions, name the library, the attributes or namespace affected, and why
it can't be fixed (latest version and the `OTEL_SEMCONV_STABILITY_OPT_IN` opt-in both fall short).
Frame it as an accepted gap with a reason, not a failure — and where one exists, point at the
upstream version or issue that would close it.

Finally, end with a list of environment variables that the user should set to send telemetry to an endpoint. At a minimum, this would include `OTEL_EXPORTER_OTLP_ENDPOINT` with optionally `OTEL_EXPORTER_OTLP_HEADERS` to do any authentication. If headers like `OTEL_SEMCONV_STABILITY_OPT_IN` and `OTEL_SERVICE_NAME` are needed and not set in existing startup scripts, they need to be mentioned as well.
