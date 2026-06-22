---
name: otel-verification
description: >
  Independently verify that an application's OpenTelemetry instrumentation actually
  emits correct telemetry — by running the app, generating real traffic, capturing the
  emitted spans to a file, and checking them against a contract. Needs no backend and no
  collector. Trigger phrases: "verify my instrumentation", "check my telemetry",
  "are my spans correct", "verify the OTel output", "did the instrumentation work",
  "validate my spans", "check semantic conventions", or any request to confirm that
  emitted OpenTelemetry telemetry is correct. Also used as the verification hand-off from
  the otel-instrumentation skill.
metadata:
  version: "1.0.0"
---

# OpenTelemetry Verification

Confirm that instrumentation **actually produces correct telemetry** — not that the code
looks right or that the app boots.

## Core principle: verify the telemetry, not the intent

Treat the instrumentation as **unverified until proven**. Judge it only from the spans the
application emits under **real traffic** — never from reading the source, and never from the
app merely starting or importing cleanly. The most common false pass is "the app starts, so
it's instrumented"; an app can start perfectly and still emit zero spans, legacy attribute
names, or broken (orphaned) traces. If you did not see the spans, you have not verified.

This skill is **offline**: it captures spans locally via a file/console exporter, so it needs
no OTLP backend and **no collector to install or configure**. (To verify against a backend
instead — querying traces that already reached Honeycomb — use the `verify-recent-trace`
skill; this skill is the local, backend-free counterpart.)

## Procedure

### 1. Add a file/console span exporter

Export spans to a file or the console, **in addition to** any OTLP exporter, so you can read
them directly. Simplest is the standard autoconfiguration env var (honored by the SDKs and the
OTel Java agent), which takes a comma-separated list:

```
OTEL_TRACES_EXPORTER=otlp,console
```

If the SDK/agent has no console/file exporter, add a second span processor in code wired to
one — and **remove it again once verification passes**:

- **Python:** `BatchSpanProcessor(ConsoleSpanExporter(out=open("spans.json","w")))` from
  `opentelemetry.sdk.trace.export`.
- **Go:** `stdouttrace.New(stdouttrace.WithWriter(f))`
  (`go.opentelemetry.io/otel/exporters/stdout/stdouttrace`).
- **Java (agent):** `OTEL_TRACES_EXPORTER=otlp,console` — no code change.
- **Node:** `ConsoleSpanExporter` from `@opentelemetry/sdk-trace-base`.

Capture the output to a file you can read (e.g. redirect the app's stdout, or write the
exporter to a path).

### Don't guess how to run the app — use the provided commands, or ask

Knowing exactly **how to start the app** and **how to exercise it end-to-end** is what makes
verification real; guessing is what makes it hollow (or breaks things — wrong ports, missing
env). Resolve both before proceeding, in this order:

1. **Use what you were given.** If your task/prompt provides a start command, the ports to bind,
   and/or an end-to-end traffic/test command or script, use exactly those. (For example, a
   harness may pass a start command, the ports, and a bundled traffic script in the checkout.)
2. **Otherwise ask the user**: "How do I start your app (command + ports)?" and "How do I
   exercise it end-to-end (a test/traffic command, or the key routes)?" Do not guess these.

### 2. Start the application the way it really runs

Launch it with the provided/answered start command, binding the specified ports, so
auto-instrumentation initializes exactly as in production. Confirm the required env vars
(`OTEL_SEMCONV_STABILITY_OPT_IN`, `OTEL_SERVICE_NAME`, …) are set **before** the process starts.

### 3. Generate real traffic — this is mandatory

Run the provided end-to-end/traffic command (or, if you were given routes, hit them), issuing
**actual requests** that exercise every instrumented path:

- Hit each HTTP route (with a real client: `curl`, `httpx`, `requests`, a browser driver, …).
- Trigger the database operations (the requests above should, or call the code paths directly
  through the running app).
- Exercise the custom/business operations you expect to produce spans.

**These do NOT count as verification:** importing or starting the app; unit tests that don't
route through the running server's instrumentation; reading the code. If you genuinely cannot
generate traffic in this environment, **say so and report the verification as blocked** — do
not report a pass.

### 4. Read the captured spans and check the contract

Read the span file/output and confirm every item. This is a required checklist:

- [ ] **Spans exist** for each operation you exercised (HTTP routes, DB queries, custom work).
- [ ] **Current semantic conventions** — the stable names are present
  (`http.request.method`, `http.response.status_code`, `url.path`, `url.full`,
  `db.query.text`, `db.system.name`, `server.address`, `network.peer.address`, …) and the
  legacy names are **absent**: grep the spans for `http.method`, `http.status_code`,
  `http.url`, `http.target`, `http.host`, `http.scheme`, `http.flavor`, `http.user_agent`,
  `net.peer.ip`, `net.peer.port`, `net.host.port`, `db.statement`, `db.system`, `db.name`,
  `enduser.id`. Any hit is a FAIL — the opt-in didn't take effect or the instrumentation
  library is too old.
- [ ] **Resource attributes** include `service.name` (not `unknown_service`) and
  `service.version`.
- [ ] **Business attributes** the instrumentation was supposed to add are present, with the
  intended names.
- [ ] **Trace structure** is connected — spans from one request share a trace id and parent
  correctly; there are **no** unexpected root/orphan spans (a sign of broken context
  propagation).
- [ ] **Exceptions/outcomes** are recorded on spans where errors occur (exercise an error path
  to confirm).

### 5. Report a verdict with evidence

Report **PASS** only if every check passes. Otherwise report **FAIL** and, for each failed
check, the concrete evidence — the exact legacy attribute names observed, which operations
produced no spans, which spans were orphaned — so the instrumentation can be fixed. Vague
"looks good" is not a verdict; cite the spans.

If invoked as a hand-off from instrumentation: return this verdict to the caller. The
instrumentation is **not complete** until verification returns PASS; on FAIL, the findings
must be fixed and verification re-run.
