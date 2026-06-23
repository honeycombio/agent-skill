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
application emits under **real traffic** — never from reading the source, and never from the app
merely starting or importing cleanly. An app can start perfectly and still emit zero spans, legacy
attribute names, or orphaned traces. **If you didn't see the spans, you haven't verified.**

This skill is **offline and backend-free**: it captures spans locally with the SDK's or agent's own
exporter, so it needs no OTLP backend (no Honeycomb) and no collector. (To verify against traces that
already reached Honeycomb, use the `verify-recent-trace` skill instead.)

## Procedure

### 1. Find out how to start and exercise the app

Knowing exactly how to start the app and how to drive it end-to-end is what makes verification real;
guessing wrong ports or env makes it hollow. Resolve both before going further:

1. **Use what you were given.** If your task provides a start command, the ports to bind, and/or an
   end-to-end traffic/test command or script, use exactly those.
2. **Otherwise ask the user:** "How do I start your app (command + ports)?" and "How do I exercise it
   end-to-end (a test/traffic command, or the key routes)?"

### 2. If a `weaver/` registry exists, start a weaver live-check receiver

When the implementer created a `weaver/` directory and the `weaver` CLI is available, run the
telemetry through a registry live-check — it catches attribute-naming defects the manual span review
can't (a custom attribute under a standard namespace, a misnamed attribute). weaver receives telemetry
over OTLP, so start it **before** the app, on **free ports** so concurrent verifications don't collide:

```
GRPC=$(python3 -c 'import socket;s=socket.socket();s.bind(("",0));print(s.getsockname()[1]);s.close()')
ADMIN=$(python3 -c 'import socket;s=socket.socket();s.bind(("",0));print(s.getsockname()[1]);s.close()')

weaver registry live-check --registry weaver \
  --input-source otlp --otlp-grpc-port "$GRPC" --admin-port "$ADMIN" \
  --format json --output ./weaver-report &
```

**Do not pass `--include-unreferenced`** — a correct registry imports the upstream semconv groups it
builds on, so standard attributes resolve on their own; the flag would mask a registry that doesn't.

No registry? Skip this step — the span capture below is all you need.

### 3. Set up span capture

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

If you started weaver in step 2, also send spans to it: keep `otlp` in the exporter list and point it
at weaver — `OTEL_TRACES_EXPORTER=otlp,<local exporter>`, `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:$GRPC`,
`OTEL_EXPORTER_OTLP_PROTOCOL=grpc`. One traffic run then feeds both the span file and weaver.

The clean span file (`spans.json` / `spans.jsonl`, one record per line) is what you inspect in step 6.

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

### 6. Check the span contract

Read the span file and confirm every item:

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
- [ ] **Registry conformance** (if weaver is running) — zero `violation`-level advice (step 7).

### 7. Read the weaver verdict (if you started it)

Finalize the live-check and read the report:

```
curl -X POST "http://localhost:$ADMIN/stop"    # writes ./weaver-report/live_check.json
```

Inspect `statistics.advice_level_counts`. Any **`violation`** is a **FAIL** — cite the offending
attribute. Common ones:

- A **`missing_attribute`** ("attribute … does not exist in the registry"). **Every one is a FAIL —
  including attributes the app's own code never sets**, i.e. ones emitted by an instrumentation library
  or the runtime (`asgi.event.type`, framework/host/process attributes, …). The registry is meant to be
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

Report **PASS** only if every check passes. Otherwise report **FAIL** and, for each failed check, the
concrete evidence — the exact legacy attribute names observed, which operations produced no spans, which
spans were orphaned — so the instrumentation can be fixed. "Looks good" is not a verdict; cite the spans.

If invoked as a hand-off from instrumentation, return this verdict to the caller: the instrumentation is
**not complete** until verification returns PASS; on FAIL, the findings must be fixed and verification
re-run.
