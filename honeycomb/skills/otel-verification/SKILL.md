---
name: otel-verification
description: >
  Assess how good an application's observability is: judge the telemetry it emits — in Honeycomb —
  against what good observability looks like, producing a verdict, reproducible evidence, and the
  gaps that remain. Judges telemetry already flowing, or (with your go-ahead) runs the app to
  generate fresh test telemetry first; works whether the instrumentation was just added or is
  already live in production. Entirely optional and standalone.
  Trigger phrases: "verify my instrumentation", "check my telemetry",
  "is my instrumentation any good", "are my spans correct",
  "are my metrics arriving", "are my logs exported",
  "verify the OTel output", "did the instrumentation work",
  "validate my spans", "check semantic conventions",
  or any request to confirm or assess emitted OpenTelemetry telemetry.
metadata:
  version: "0.3.0"
---

# OpenTelemetry Verification

Judge how good an application's observability is: does the telemetry it emits actually make the app
debuggable in production? You judge telemetry **in Honeycomb**. The data is either already there —
from a just-completed instrumentation run, or real traffic already flowing — or, **with the user's
go-ahead, you run the app to generate fresh test telemetry first** (see step 1). Running the app is an
option you offer, never a default; when you judge data that already exists you change nothing.

You did not write the instrumentation, and you must not assume it is correct — judge only what the
emitted telemetry shows.

## Before you start

You need:

- **which environment & service to look at** — the Honeycomb environment, and the `service.name` to assess (required). Key off `service.name`, not a single dataset — a service's metrics land in a *different* dataset from its traces, and `service.name` spans them all
- **query access** — the Honeycomb MCP, *or* a Honeycomb *query* API key (read access) if the MCP isn't available
- *(optional)* **the app's repo** (read-only) — lets you compare what the code *could* expose against what it actually emits, to find valuable context that isn't sent yet
- *(optional)* **the org's attribute standards** — a weaver registry or conventions doc to check against; otherwise judge against OpenTelemetry semantic conventions
- *(optional)* **focus** — a specific thing to check ("is tenant on every request?"); otherwise sweep broadly
- *(only if you will run the app for fresh telemetry)* **how to start it, drive representative traffic, and the export env** (`OTEL_EXPORTER_OTLP_ENDPOINT` and any `OTEL_EXPORTER_OTLP_HEADERS`, `OTEL_SERVICE_NAME`) — discover from the repo or ask
- *(only if you will run a weaver live-check on a live stream)* **`weaver` and an OTel collector installed** — the app exports through the collector, which fans telemetry to weaver's live-check receiver

If you are judging data that already exists and none is arriving at all, you cannot judge — report
that (**BLOCKED**) and offer to run the app (step 1), or point back at instrumentation.

## Steps

Work in four passes: **choose** how to source the telemetry (and, if asked to, run the app),
**gather** reproducible evidence from it, **score** each named test below, then **report** the
verdict and findings. Every test scores **PASS**, **FAIL**, or **N/A**, and carries the specific
finding(s) that justify anything other than PASS.

### 1. Choose how to source the telemetry

Before gathering anything, ask the user two questions and proceed on their answers:

1. **Fresh telemetry or existing?** — *"Should I run the app now to generate fresh test telemetry,
   or judge the telemetry already in Honeycomb?"* Default to judging what already exists; only run the
   app if the user wants it (or nothing is arriving and they'd rather generate some than be BLOCKED).
2. **Weaver checks or Honeycomb-only?** — *"Include weaver semantic-convention checks (needs `weaver`
   and an OTel collector installed), or judge from Honeycomb queries only?"* If they decline, or the
   toolchain isn't available, skip weaver: `weaver_custom_attrs` and `weaver_missing_attrs` score
   **N/A** and you note weaver was not run.

**If the user asked you to run the app**, do it now, then gather from the telemetry it produces:

- Start the app with the **export configuration active** — the `OTEL_*` variables (`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`, `OTEL_SERVICE_NAME`, and `OTEL_SEMCONV_STABILITY_OPT_IN` if the instrumentation needs it); without them nothing reaches the destination and there is nothing to judge.
- **If weaver checks are also on**, point the app's OTLP export at a **local collector** that fans telemetry out to both Honeycomb (so you can query it) and a `weaver registry live-check` receiver (so weaver judges the live stream) — see **[references/weaver-live-check.md](references/weaver-live-check.md)** for that setup.
- Wait for readiness with a **bounded poll** — loop on a concrete signal (a startup log line, a health endpoint, the port accepting connections) with a timeout, and bail early if the process has exited — not a foreground `tail -f` or a fixed `sleep` guess.
- Drive **real, representative traffic**. If you drive or spot-check endpoints yourself, **resolve their real paths from the routing config first** — the mount prefix and route registration, read in full, not a guessed URL. A guessed path 404s, and its HTML error body also breaks any `jq`/variable extraction downstream.
- Before reading telemetry back, wait for the exporter to **flush** — watch for its own confirmation or use a single bounded wait sized to the batch interval, not a blind sleep.

Otherwise, skip straight to gathering from the telemetry already in Honeycomb.

### 2. Gather the evidence

Each check is a Honeycomb query you run now and the user can re-run later — these queries *are* the
evidence in your report. Use the Honeycomb MCP (`list_spans`, `get_span_details`, `run_query`, …)
where available.

**Query lean.** Every result you pull stays in your context for the rest of the session, so ask each
query for the least that answers the check. Reach first for the discovery tools — `list_spans` to see
what spans exist, `get_span_details` to see which attributes a span populates and their top values —
they return compact summaries. Use `run_query` for the specific calculation a check needs: an
*existence* check is a `COUNT` filtered to the attribute, not a wide breakdown. A `COUNT` broken down
across many columns with a high limit returns a large table you then carry for the whole run — only
break down when you actually need the cross-tabulation, and keep the columns and limit to what the
check requires.

**Is anything arriving at all?** Count events for the service over a recent window. If nothing is
arriving and you did **not** run the app, stop — the verdict is **BLOCKED** and no tests are scored;
offer to run the app (step 1) or point back at instrumentation. If you **did** run the app under
traffic and still nothing arrived, that is a broken export pipeline — a real defect: `has_traces`
(and whichever signal is missing) **FAIL**, not BLOCKED.

Otherwise gather what each test needs:

- **Signals present** (`has_traces`, `has_logs`, `has_metrics`) — check for all three, keying off `service.name`, across datasets (metrics and logs land in *separate* datasets from traces). Report the count of each; a missing pipeline usually means it was never wired (a common miss is logs — the app writes to stdout but nothing bridges to an OTLP log exporter). Confirming metrics is a two-query flow — don't guess the dataset or break down by metric name: (1) `get_environment` and find the dataset whose `dataset_type = metrics` (do **not** invent a slug like `<service>-metrics` or match on "metrics" in the name); (2) `run_query` that dataset with `COUNT_DATAPOINTS` filtered to `service.name = <service>` over a recent window; non-zero means metrics flow.
- **Service identity** (`has_service.name`) — group by `service.name`: set, correct, not the `unknown_service` default.
- **Traces well-formed** (`all_root_spans`, `no_missing_spans`) — a broken trace has child spans but no root. Catch it in one query with Honeycomb's relational fields: `COUNT` filtered to `none.trace.parent_id does-not-exist` **and** `any.trace.parent_id exists` — traces with a parented span but no root. That count is `all_root_spans`'s evidence and should be **0**. Then pull a few sample traces and walk them by eye for gaps where expected work simply isn't there — that's `no_missing_spans`.
- **HTTP span names** (`has_http.route`) — for an HTTP service, `http.route` is present on server spans, so span names stay low-cardinality instead of falling back to full URLs.
- **Conventions** (`latest_semconv`) — span and attribute names follow the *current* stable semantic conventions, not deprecated or superseded names (conventions get renamed as they stabilise — e.g. the HTTP attributes). Look them up rather than assume: `search_semconv`, `get_semconv_attribute`; flag outdated ones.
- **Registry check** (`weaver_custom_attrs`, `weaver_missing_attrs`, *only when weaver checks are on and a weaver registry was provided*) — let weaver compare the attributes the service **actually emits** against the registry so you don't eyeball it. There are two ways to feed weaver, keyed by how you sourced the telemetry (step 1):
  - **Ran the app** → weaver judged the **live stream** through the collector's live-check receiver as traffic flowed; read the verdict from its report.
  - **Judging existing Honeycomb data** → build a **JSON sample** of the emitted attributes (`get_dataset_columns` / `find_columns` across the trace, metric, and log datasets that received data recently) and run `weaver registry live-check` against that file — no live stream, no app boot.

  The full procedure for both — the collector wiring, building the sample file, the exact `weaver registry live-check` invocation and flag guidance, and reading the verdict from `statistics` — is in **[references/weaver-live-check.md](references/weaver-live-check.md)**. Either way, split the result: **custom attributes the app emits** that are undocumented-in-registry *or* wrong-typed feed `weaver_custom_attrs`; **registry-declared attributes never emitted**, plus standard-semconv attributes emitted but not referenced, feed `weaver_missing_attrs`. If weaver checks are off, skip this and score both **N/A**.
- **Depth & usefulness** (`clean_traces`, `business_context`) — the checks above confirm the plumbing; this asks whether the data is actually *useful*. No fixed query list — explore, scoped to the **focus** if one was given, otherwise broadly:
  - Open real traces end to end. Can you tell what the app did and why? Are the traces **tidy** — no junk single-span or noise traces, no swarm of stray roots, work grouped sensibly (e.g. startup migrations under one root)? → `clean_traces`
  - Are spans **wide** — carrying the business and high-cardinality context that answers a real debugging question ("which tenant saw these errors?", "what slowed this request?") — or just generic defaults? Read a span's attributes with `get_span_details`, not a wide multi-column breakdown. **If the repo is provided**, compare what the code *could* surface (domain entities, decisions, identifiers it holds) against what the telemetry carries, and flag valuable context that isn't emitted. → `business_context`

**Errors are untested, not scored.** *If* the window contains failed operations, confirm they carry
error status and exception detail rather than reporting silent success. But **no errors in the window
is neither PASS nor FAIL** — they may simply not have happened, and you cannot confirm error
instrumentation from telemetry that contains none. Note it as untested coverage.

### 3. Score

Assign every test below a **PASS**, **FAIL**, or **N/A**. The **overall verdict is PASS only if every
_critical_ test is PASS** (an N/A does not block). Any critical **FAIL** makes the run **FAIL**.
Improvement tests never change the verdict — they are reported as findings to act on. If nothing was
arriving to judge, the verdict is **BLOCKED** and nothing below is scored.

**Critical** — the telemetry is not trustworthy unless all of these pass:

| Test | PASS means | FAIL / N/A |
|---|---|---|
| `has_traces` | trace spans arriving for the service | FAIL if none — never N/A |
| `has_logs` | log records arriving for the service | FAIL if none; **N/A only when explicitly told to ignore logs** |
| `has_metrics` | metric datapoints arriving for the service | FAIL if none; **N/A only when explicitly told to ignore metrics** |
| `has_service.name` | `service.name` set and correct | FAIL if missing or `unknown_service` |
| `all_root_spans` | no orphaned traces — the relational query returns 0 | FAIL if any trace has spans but no root |
| `no_missing_spans` | sampled traces show no gaps in expected work | FAIL if expected spans are absent |
| `has_http.route` | `http.route` present on HTTP server spans | FAIL if absent; N/A only if the service has no HTTP surface |
| `weaver_custom_attrs` | every custom attribute the app emits is in the registry **and** correctly typed | FAIL on any undocumented-emitted or mistyped custom attr; N/A if weaver checks are off or no registry was provided |

**Improvements** — findings that sharpen the telemetry but do not gate the verdict:

| Test | PASS means | Finding when |
|---|---|---|
| `latest_semconv` | names use current stable semconv | deprecated or superseded names in the current data |
| `weaver_missing_attrs` | registry and standard refs fully covered | registry-declared attrs never emitted, or standard attrs emitted but unreferenced (N/A if weaver checks are off) |
| `clean_traces` | traces are tidy and sensibly grouped | junk single-span or noise traces, stray roots, poor grouping |
| `business_context` | spans are wide with useful business context | generic-only spans; context the code holds but does not emit |

### 4. Report

Lead with the verdict, then the findings — the actionable part. Deliver:

- **The verdict** — **PASS**, **FAIL**, or **BLOCKED** — followed by a **per-test result table** covering both sections, each test marked PASS / FAIL / N/A. The critical section alone determines the verdict.
- **The findings** — grouped under the test they belong to. Give each as **one tight entry**: the problem, where it is, and the single query or trace that demonstrates it — no transcript. Where a finding stems from a library that can't emit the current convention, say so, so the reader can reconcile rather than chase it.
- **Reproducible evidence** — a *few* representative queries, not an exhaustive transcript: enough that the reader can see it themselves rather than take your word.

This is the user's audit: include the verdict, the per-test table, the findings, and the demonstrating
queries. If weaver checks were skipped, say so and mark those tests N/A so the reader knows the
registry was not live-checked. If you ran the app to generate the telemetry, note that too, so the
reader knows the data reflects a test run rather than production traffic.
