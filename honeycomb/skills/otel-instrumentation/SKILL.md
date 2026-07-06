---
name: otel-instrumentation
description: >
  Make an application observable: add OpenTelemetry instrumentation so the app emits traces,
  metrics, and logs that make it debuggable in production, following current semantic conventions
  and documented in a weaver registry, and send them to Honeycomb.
  Trigger phrases: "instrument my app", "add tracing",
  "set up OpenTelemetry", "configure OTel", "add custom spans",
  "add attributes to spans", "send traces to Honeycomb",
  "set up OTLP", "add span events",
  "add span links", "set up tracing for [any language]",
  "configure the OTel Collector",
  or any request about OpenTelemetry SDK setup, custom instrumentation,
  or sending data to Honeycomb.
metadata:
  version: "0.3.0"
---

# OpenTelemetry Instrumentation

Make the target application observable: running the way it normally runs, it should emit traces,
metrics, and logs that follow current OpenTelemetry semantic conventions and carry the business
context needed to debug it in production. **Follow current semantic conventions and document every
attribute you emit in a weaver registry.**

## Before you start

Establish the following before changing code. Some arrive with your task; discover the rest from the
repo. **Collect everything you still need into a single batch of questions, put them to the user up
front, and confirm a short plan — then implement.** Don't drip-feed questions mid-implementation,
and don't guess at anything only the user knows.

- **repo path** — the app to instrument
- **service name** — the `service.name` / Honeycomb dataset the telemetry uses (ask if not given; never invent one)
- **language + runtime**, and the **frameworks** in play (HTTP server, DB client, ORM, queue) — discover from the repo
- **how to build and run** the app — discover or ask; you need it to wire dependencies, place export env vars in the right startup scripts, and tell the user how to run it at handback
- **what the app does and what the user cares about debugging** — this drives the business context
- **attribute standards** — ask whether the org has a registry or document that *defines existing attributes and their values* (a **weaver registry**, or an established conventions page) to look up and reuse verbatim — alongside the OpenTelemetry semantic conventions
- **naming conventions** — ask the rules for *creating a new* attribute when no standard one fits (namespace/prefix, casing, structure); default to an `app.*` namespace if there are none
- **focus** — optionally a specific area to prioritise; otherwise cover the app broadly

## Steps

### 1. Gather

Read the repo to establish the language, frameworks, entry points, and how it builds and runs.
**Read economically** — everything you read stays in your context for the whole run. Locate the code
you need by searching (grep/glob) and read narrowly around the hits; don't read or `cat` whole files
when a targeted range will do. You are looking for the handful of places instrumentation attaches —
entry points, framework wiring, and the handlers/services where business context is available — not
a complete mental model of every file.
Confirm the service name with the user. Wire export through the **standard OTLP environment
variables** — `OTEL_EXPORTER_OTLP_ENDPOINT` for the destination and `OTEL_EXPORTER_OTLP_HEADERS` for
any auth (e.g. `x-honeycomb-team=<ingest key>` for Honeycomb) — so the app honours them at runtime.
Never hardcode an endpoint or a key; the user supplies those when they run it (you list them at
handback, step 6).

### 2. Enable auto-instrumentation

**Read the language-specific reference for your app before wiring anything** — it gives the concrete
packages, provider/exporter wiring, logs bridge, and the traps that matter for that language, and
**where it differs from the generic guidance in this skill, the language reference wins**:
**[Java](references/java.md)** · **[Python](references/python.md)** · **[Go](references/go.md)**. If
there is no reference for the app's language, follow the generic guidance below.

Get the app emitting **all three signals — traces, metrics, and logs** — out of the box. Where the
language offers a
zero-code auto-instrumentation agent (e.g. Java, Python, Node, .NET), prefer it; otherwise wire up
the OpenTelemetry SDK with the standard framework instrumentations. Keep custom code to a minimum —
take the least-custom path the language and framework support. Set the service identity —
`service.name`, plus `service.version` where readily available. This is one knob, not two: prefer the
`OTEL_SERVICE_NAME` environment variable (the default path, and the only one for zero-code agents)
over setting it in code, and list it consistently with the other export env vars in the handback.

**A signal only counts if it is actually exported — wire each pipeline end to end.** A zero-code agent
normally covers all three; an SDK setup must wire each one explicitly, and it is easy to build a
pipeline that emits nothing. **Logs** are the usual casualty, because a working log pipeline is a full
chain: *the logger the app already uses* → an OTel bridge/handler → a `LoggerProvider` → an OTLP log
exporter. Two half-configurations look done but export zero records: enabling only log/trace
**correlation** (injecting trace IDs into log lines) with no export pipeline; or standing up a
`LoggerProvider` + exporter but never **bridging** the app's real logger to it, so it keeps writing to
stdout. **Metrics** have the same shape — a `MeterProvider` with an OTLP metric exporter, not just
instruments. Don't assume; trace each signal's pipeline in the code end to end — provider →
exporter, and for logs the bridge from the app's real logger — and confirm all three are wired
before you hand off.

**Declare the new dependencies in the project's manifest, not just the live environment.** Add the
OpenTelemetry packages the way the project declares its other dependencies (`uv add` / `pyproject.toml`,
`go get`, `package.json`, `pom.xml`) and update the lockfile, so a clean checkout running the project's
canonical install reproduces the instrumented dependency set. If the manifest install fails because the
new packages conflict with an existing dependency, resolve the conflict — adjust a pin, scope the
conflicting package to an optional group you exclude, or pick compatible versions.

Lastly, check whether the OpenTelemetry libraries in use emit the **current** semantic conventions.
When one emits deprecated attributes, don't stop at what its installed version does — the installed
pin is a starting point, not a fixed constraint. For each such library, in order:

1. **Upgrade** — look up the latest released version and which conventions it emits; if it emits the
   current ones, move to it (bump the manifest + lockfile).
2. **Opt in** — otherwise, check whether a value of `OTEL_SEMCONV_STABILITY_OPT_IN` (or other config)
   moves it onto the current conventions; if so, set it, add it to any startup scripts, and note it
   in the final report.
3. **Accept as a known limitation** — only when the **latest released** version still emits the old
   names and no opt-in or config can move it (you can't ship changes to a dependency). Record the
   library, the attributes/namespace affected, and **the version you confirmed still emits them** —
   stating that version is required, since "the installed version doesn't support it" is never
   sufficient and is the exact shortcut this guards against. Disclose it in the handback (step 6).

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
itself; proving it matches the *emitted* telemetry (a weaver live-check against real data) is the job
of the optional `otel-verification` skill — see the handback (step 6).

### 6. Hand back

Your job is the instrumentation itself — the code changes and a statically-valid registry. You do
**not** boot the app or drive traffic to prove it; that (and any judgement of the emitted data) is the
job of the optional `otel-verification` skill, or of the user simply running their app. Hand back with
everything they need to run it and see the result.

Lead with the outcome, not a diff: tell the user, in plain language, **what they will be able to see
and ask** once the app runs with these changes — tied to the things they said matter. Briefly
summarise **what changed** in their code so they know what landed.

**Tell them how to run it and light up the data.** Give the start command, how to generate
representative traffic, and the environment variables the app must have set to export telemetry — at
minimum `OTEL_EXPORTER_OTLP_ENDPOINT`, plus `OTEL_EXPORTER_OTLP_HEADERS` for any authentication. Also
mention `OTEL_SEMCONV_STABILITY_OPT_IN` and `OTEL_SERVICE_NAME` if they are needed and not already set
in the startup scripts. Once they run it and drive traffic, the telemetry flows to their destination.

**Call out any known limitations explicitly.** For each subsystem where an un-upgradable library
still emits deprecated conventions, name the library, the attributes or namespace affected, and why
it can't be fixed (latest version and the `OTEL_SEMCONV_STABILITY_OPT_IN` opt-in both fall short).
Frame it as an accepted gap with a reason, not a failure — and where one exists, point at the
upstream version or issue that would close it.

**Optional next step — independent verification.** To audit how good the emitted telemetry actually
is — and, if they like, generate fresh test telemetry by running the app — the user can run the
`otel-verification` skill against this `service.name`. It reads the emitted data and judges it against
current semantic conventions (and, optionally, a weaver live-check against the registry you authored),
returning a verdict and findings. It is entirely optional; nothing here depends on it.
