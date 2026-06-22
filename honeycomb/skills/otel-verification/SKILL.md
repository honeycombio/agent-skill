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

If the implementer created a **weaver registry** (a `weaver/` directory) and the `weaver`
CLI is available, also capture the telemetry into a live-check against that registry — this
is what catches attribute-naming defects the manual span review can't (a custom attribute
placed under a standard namespace, a misnamed attribute). weaver consumes telemetry over
OTLP, so start it as a receiver **before** you launch the app and point the app's OTLP
exporter at it (this is still backend-free — weaver is a local CLI, not a collector):

```
# start the receiver; it writes a JSON report when you POST /stop
weaver registry live-check --registry weaver \
  --input-source otlp --otlp-grpc-port 4317 --admin-port 4320 \
  --format json --output ./weaver-report &
```

Then in step 2 launch the app with `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317`,
`OTEL_EXPORTER_OTLP_PROTOCOL=grpc`, and `OTEL_TRACES_EXPORTER=otlp,console` so the same
traffic run feeds both the console file (for the checks below) and weaver. **Do not pass
`--include-unreferenced`** — a correct registry imports the upstream semconv groups it
builds on, so standard attributes resolve on their own; the flag would mask a registry that
doesn't.

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
- [ ] **Registry conformance** (when a `weaver/` registry exists) — the weaver live-check
  report shows **zero `violation`-level advice** (see step 5).

### 5. Check telemetry against the weaver registry (when one exists)

If you started a weaver live-check receiver in step 1, finalize it and read the verdict:

```
curl -X POST http://localhost:4320/stop        # weaver writes ./weaver-report/live_check.json
```

Inspect `statistics.advice_level_counts` in the report. Treat any **`violation`** as a
**FAIL**, and cite the offending attribute. The common ones:

- An attribute defined under a standard semconv namespace (e.g. `db.rows_affected`
  colliding with the imported `db.*`) — it must move to your own `app.*` namespace or reuse
  the standard attribute (`db.response.returned_rows`).
- A custom name that should have reused a standard semconv attribute.

**Not** failures: `improvement`-level advice (e.g. `stability: development` on your own
custom attributes), and attributes emitted by instrumentation libraries but absent from
semconv (e.g. `asgi.event.type`) or injected by the runtime (host/process resource
attributes). If `total_entities` is 0, weaver received no telemetry — treat that like
"no spans", not a pass.

### 6. Report a verdict with evidence

Report **PASS** only if every check passes. Otherwise report **FAIL** and, for each failed
check, the concrete evidence — the exact legacy attribute names observed, which operations
produced no spans, which spans were orphaned — so the instrumentation can be fixed. Vague
"looks good" is not a verdict; cite the spans.

If invoked as a hand-off from instrumentation: return this verdict to the caller. The
instrumentation is **not complete** until verification returns PASS; on FAIL, the findings
must be fixed and verification re-run.
