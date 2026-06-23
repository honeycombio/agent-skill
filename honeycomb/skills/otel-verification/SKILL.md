---
name: otel-verification
description: >
  Independently verify that an application's OpenTelemetry instrumentation actually
  emits correct telemetry — by running the app, generating real traffic, capturing the
  emitted telemetry (spans, metric datapoints, and log records) to a file, and checking
  it against a contract. Needs no backend and no
  collector. Trigger phrases: "verify my instrumentation", "check my telemetry",
  "are my spans correct", "are my metrics arriving", "are my logs exported",
  "verify the OTel output", "did the instrumentation work",
  "validate my spans", "check semantic conventions", or any request to confirm that
  emitted OpenTelemetry telemetry is correct. Also used as the verification hand-off from
  the otel-instrumentation skill.
metadata:
  version: "1.2.3"
---

# OpenTelemetry Verification

Confirm that instrumentation **actually produces correct telemetry** — not that the code
looks right or that the app boots.

## Core principle: verify the telemetry, not the intent

Treat the instrumentation as **unverified until proven**. Judge it only from the telemetry the
application emits under **real traffic** — all three signals: **spans, metric datapoints, and log
records** — never from reading the source, and never from the app merely starting or importing
cleanly. An app can start perfectly and still emit zero spans, no metrics, no logs, legacy
attribute names, or orphaned traces. **If you didn't see the telemetry, you haven't verified.**

This skill is **offline and backend-free**: it captures telemetry locally with the SDK's or agent's
own exporters, so it needs no OTLP backend (no Honeycomb) and no collector. (To verify against
telemetry that already reached Honeycomb, use the `verify-recent-trace` skill instead.)

## Procedure

### 1. Find out how to start and exercise the app

Knowing exactly how to start the app and how to drive it end-to-end is what makes verification real;
guessing wrong ports or env makes it hollow. Resolve both before going further:

1. **Use what you were given.** If your task provides a start command, the ports to bind, and/or an
   end-to-end traffic/test command or script, use exactly those.
2. **Otherwise ask the user:** "How do I start your app (command + ports)?" and "How do I exercise it
   end-to-end (a test/traffic command, or the key routes)?"

### 2. If a `weaver/` registry exists, the live-check is MANDATORY

**If the implementer created a `weaver/` directory, you must run a registry live-check — it is not
optional, and you cannot return PASS without one.** The live-check is the *only* thing that catches an
entire class of defects the manual review by eye cannot: an undeclared attribute or metric
(`missing_attribute` / `missing_metric`), a custom attribute colliding with a standard namespace, a
type mismatch. Inspecting the captured telemetry yourself is **not** a substitute — a registry can be
present and still violated, and only weaver will tell you. (Running `weaver registry check` is also not
a substitute: that validates the registry *files* statically; only `weaver registry live-check`
compares them against the telemetry the app actually emits.)

**First, a deterministic gate the live-check can't fool.** The most common and most damaging registry
defect is a missing/misplaced `imports` block — it makes the live-check flag *every* standard
attribute. A live-check run with `--include-unreferenced`, or pointed at the wrong registry, hides
exactly this; `weaver registry resolve` cannot be fooled. Run it first, against the checkout's
registry:

```bash
# point -r at the checkout's registry dir (the one holding manifest.yaml)
weaver registry resolve -r weaver --format json | grep -q 'http.request.method' \
  && echo 'imports OK' || echo 'IMPORTS MISSING'
```

`IMPORTS MISSING` is an immediate **FAIL** — report it and do not let a clean live-check override it.
This catches only the imports defect, so still run the full live-check below for everything else.

weaver receives telemetry over OTLP, so start it **before** the app, on **free ports** so concurrent
verifications don't collide:

```
GRPC=$(python3 -c 'import socket;s=socket.socket();s.bind(("",0));print(s.getsockname()[1]);s.close()')
ADMIN=$(python3 -c 'import socket;s=socket.socket();s.bind(("",0));print(s.getsockname()[1]);s.close()')

weaver registry live-check --registry weaver \
  --input-source otlp --otlp-grpc-port "$GRPC" --admin-port "$ADMIN" \
  --format json --output ./weaver-report &
```

**Do not pass `--include-unreferenced`** — a correct registry imports the upstream semconv groups it
builds on, so standard attributes resolve on their own; the flag would mask a registry that doesn't.

No `weaver/` registry in the checkout? Only then skip this step — the telemetry capture below is all
you need. If a registry *is* present, this step is required for a PASS verdict.

### 3. Set up telemetry capture

You need the spans as **structured records** carrying attributes **and parent/trace IDs** (the
trace-structure check depends on parents). Add a structured exporter to the app and capture its output
to a file; configure it now, before you start the app, and **remove it again once verification passes**.

Prefer an exporter that writes to a **dedicated file** — only spans, nothing to filter:

- **Python:** `BatchSpanProcessor(ConsoleSpanExporter(out=open("spans.json","w")))`
  (`opentelemetry.sdk.trace.export`)
- **Go:** `stdouttrace.New(stdouttrace.WithWriter(f))`
  (`go.opentelemetry.io/otel/exporters/stdout/stdouttrace`)

The Java agent and the Node console exporter log through stdout/stderr, mixed with app logs — each span
record is a **single JSON line**, so extract those:

- **Java agent:** use `logging-otlp` (**not** `console`/`logging`, which omit parent span IDs). It
  writes structured OTLP-JSON and ships with the agent. Set `OTEL_TRACES_EXPORTER=otlp,logging-otlp`,
  capture output with `your-start-cmd > app.log 2>&1`, then
  `grep -o '{"resourceSpans".*}' app.log > spans.jsonl`.
- **Node:** `ConsoleSpanExporter` from `@opentelemetry/sdk-trace-base`; extract the same way.

The clean span file (`spans.json` / `spans.jsonl`, one record per line) is what you inspect in step 6.

**Capture metrics and logs too.** Verification covers all three signals, so also turn on a console/file
exporter for the other two and confirm they produce output. With most SDKs and language agents the
simplest path is `OTEL_METRICS_EXPORTER=console` and `OTEL_LOGS_EXPORTER=console`. For a manual SDK
setup, add a `ConsoleMetricExporter` and a `ConsoleLogRecordExporter`. Capture each to its own file or
grep its JSON lines out of the app log, the same way as spans.

**Shorten the metric export interval for the run.** Metrics export on a 60-second periodic cycle by
default — longer than a verification run, so you'd capture zero metric datapoints even though the
instrumentation is correct. Set `OTEL_METRIC_EXPORT_INTERVAL=10000` (10s) in the launch environment so
metrics actually flush while traffic is flowing. (Traces and logs use a few-second batch cadence and
don't need this.) This is a verification-runtime concern only; don't bake a short interval into the
app's committed config.

**Feed weaver all three signals — not just traces (if you started it in step 2).** weaver's
`missing_metric` and attribute checks only fire on signals it actually receives, so routing only
traces would make the metric (and log) conformance checks silently pass on telemetry weaver never
saw. Keep `otlp` in **every** signal's exporter list and point the shared OTLP endpoint at weaver's
gRPC port, so one traffic run feeds the capture files **and** weaver across all three signals:

```
OTEL_TRACES_EXPORTER=otlp,<trace file/console exporter>
OTEL_METRICS_EXPORTER=otlp,console
OTEL_LOGS_EXPORTER=otlp,console
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:$GRPC   # weaver's gRPC port from step 2
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
```

### 4. Start the app — once

Launch it with the start command and ports from step 1, so auto-instrumentation initializes exactly as
in production. Confirm the required env vars (`OTEL_SEMCONV_STABILITY_OPT_IN`, `OTEL_SERVICE_NAME`, and
the exporter vars from steps 2–3) are set **before** the process starts.

### 5. Generate real traffic — mandatory

Run the traffic/test command from step 1 (or hit the given routes), issuing **actual requests** across
every instrumented path:

- Hit each HTTP route with a real client (`curl`, `httpx`, a browser driver, …).
- Trigger the database operations.
- Exercise the custom/business operations you expect to produce spans.
- Exercise an error path, so you can confirm exceptions are recorded.

**Not verification:** importing or starting the app; unit tests that don't route through the running
server's instrumentation; reading the code. If you genuinely cannot generate traffic here, report the
verification as **blocked** — not a pass.

### 6. Check the telemetry contract

Read the captured files and confirm every item:

- [ ] **Spans exist** for each operation you exercised (HTTP routes, DB queries, custom work).
- [ ] **Current semantic conventions present, legacy absent.** Stable names appear
  (`http.request.method`, `http.response.status_code`, `url.path`, `url.full`, `db.query.text`,
  `db.system.name`, `server.address`, `network.peer.address`, …). Grep for the legacy names and find
  **none**: `http.method`, `http.status_code`, `http.url`, `http.target`, `http.host`, `http.scheme`,
  `http.flavor`, `http.user_agent`, `net.peer.ip`, `net.peer.port`, `net.host.port`, `db.statement`,
  `db.system`, `db.name`, `enduser.id`. Any hit is a FAIL — the opt-in didn't take effect or the
  instrumentation library is too old.
- [ ] **Resource attributes** include `service.name` (not `unknown_service`) and `service.version`.
- [ ] **Business attributes** the instrumentation was meant to add are present, with the intended names.
- [ ] **Trace structure** is connected — spans from one request share a trace id and parent correctly;
  no unexpected root/orphan spans (a sign of broken context propagation).
- [ ] **Exceptions/outcomes** are recorded on spans where errors occur.
- [ ] **Metric datapoints exist** — the metrics capture is non-empty after traffic. At minimum the
  HTTP server-duration metric (`http.server.request.duration`) and any runtime/process metrics the
  agent emits should appear; an empty metrics capture means the metrics signal was never exported.
- [ ] **Log records exist** — the logs capture is non-empty, carrying the app's log lines as OTLP log
  records (with `severity`/`body`, and `trace_id`/`span_id` when emitted inside a span). An empty logs
  capture means the logging bridge isn't wired to the `LoggerProvider`.
- [ ] **Registry conformance** — if a `weaver/` registry exists, the live-check **must** have run
  and shown zero `violation`-level advice (step 7). A registry present but unchecked is an automatic
  FAIL, not a pass — you have no evidence either way.

### 7. Read the weaver verdict (whenever a registry was present)

Finalize the live-check and read the report:

```
curl -X POST "http://localhost:$ADMIN/stop"    # writes ./weaver-report/live_check.json
```

Inspect `statistics.advice_level_counts`. Any **`violation`** is a **FAIL** — cite the offending
attribute. Common ones:

- A **`missing_attribute`** ("attribute … does not exist in the registry"). **Every one is a FAIL —
  including attributes the app's own code never sets**, i.e. ones emitted by an instrumentation library
  or the runtime (framework/host/process attributes the app code never sets, …). The registry is meant to be
  a *complete* description of the telemetry the app emits, so an undeclared attribute is a real gap: it
  must be added to the registry (the fix differs by origin — see the implementation skill's
  `libraries.yaml` guidance for library/runtime attributes you don't control).
- An attribute under a standard semconv namespace (e.g. `db.rows_affected` colliding with the imported
  `db.*`) — move it to your own `app.*` namespace or reuse the standard attribute
  (`db.response.returned_rows`).
- A custom name that should have reused a standard semconv attribute.

**Not failures:** `improvement`-level advice only (e.g. `stability: development` on your own custom
attributes). If `total_entities` is 0, weaver received no telemetry — treat that as "no spans", not a
pass.

### 8. Report a verdict with evidence

Report **PASS** only if every check passes — and if a `weaver/` registry exists, only if the
live-check actually ran and came back clean (a present-but-unchecked registry is a FAIL). Otherwise
report **FAIL** and, for each failed check, the concrete evidence — the exact legacy attribute names
observed, which operations produced no spans, which spans were orphaned, whether the metrics or logs
capture was empty, the exact `missing_attribute`/`missing_metric`/type-mismatch advice from weaver — so
the instrumentation can be fixed. "Looks good" is not a verdict; cite the telemetry.

If invoked as a hand-off from instrumentation, return this verdict to the caller: the instrumentation is
**not complete** until verification returns PASS; on FAIL, the findings must be fixed and verification
re-run.
