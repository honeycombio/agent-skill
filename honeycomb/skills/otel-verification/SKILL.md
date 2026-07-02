---
name: otel-verification
description: >
  Assess how good an application's observability is: judge the telemetry it already emits — in
  Honeycomb — against what good observability looks like, producing a verdict, reproducible
  evidence, and the gaps that remain. Does not run the app or generate traffic; works whether the
  instrumentation was just added or is already live in production.
  Trigger phrases: "verify my instrumentation", "check my telemetry",
  "is my instrumentation any good", "are my spans correct",
  "are my metrics arriving", "are my logs exported",
  "verify the OTel output", "did the instrumentation work",
  "validate my spans", "check semantic conventions",
  or any request to confirm or assess emitted OpenTelemetry telemetry.
metadata:
  version: "0.1.0"
---

# OpenTelemetry Verification

Judge how good an application's observability is: does the telemetry it emits actually make the app
debuggable in production? You assess **telemetry that already exists** — you do **not** run the app
or generate traffic. The data comes from one of two places: a just-completed instrumentation run, or
real traffic already flowing to Honeycomb.

You did not write the instrumentation, and you must not assume it is correct — judge only what the
emitted telemetry shows.

## Before you start

You need:

- **which environment & service to look at** — the Honeycomb environment, and the `service.name` to assess (required). Key off `service.name`, not a single dataset — a service's metrics land in a *different* dataset from its traces, and `service.name` spans them all
- **query access** — the Honeycomb MCP, *or* a Honeycomb *query* API key (read access) if the MCP isn't available
- *(optional)* **the app's repo** (read-only) — lets you compare what the code *could* expose against what it actually emits, to find valuable context that isn't sent yet
- *(optional)* **the org's attribute standards** — a weaver registry or conventions doc to check against; otherwise judge against OpenTelemetry semantic conventions
- *(optional)* **focus** — a specific thing to check ("is tenant on every request?"); otherwise sweep broadly

If no telemetry is arriving at all, you cannot judge — report that (BLOCKED)
and point back at instrumentation.

## Steps

Judging happens in two passes: a **basic check** that is concrete and reproducible, then an
open-ended **exploration** for depth.

### 1. Basic checks — concrete and reproducible

Run a fixed set of checks, each expressible as a Honeycomb query you run now and the user can re-run
later. These queries *are* the reproducible evidence in your report. Use the Honeycomb MCP
(`list_spans`, `get_span_details`, `run_query`, …) where available.

- **Is telemetry arriving?** Count events in the environment over a recent window. If zero, stop — **BLOCKED**.
- **Which signals?** Check for **all three** — traces, metrics, and logs — keying off `service.name` and looking across datasets (metrics and logs land in separate datasets from traces, not just the trace dataset). Report the count of each. A signal with **zero** records is a **finding**, not something to pass over: for a typical service all three are expected, and a missing one usually means that export pipeline was never wired (a common failure is logs — the app writes to stdout but nothing bridges to an OTLP log exporter). Only exempt a signal if the app genuinely has no source for it, and say so explicitly.
- **Service identity** — group by `service.name`: it is set, correct, and not the `unknown_service` default.
- **Traces well-formed (non-trivial — use the relational query)** — a broken trace has child spans but no root span. Catch it in one query with Honeycomb's relational fields: `COUNT` filtered to `none.trace.parent_id does-not-exist` **and** `any.trace.parent_id exists` — traces that contain spans *with* a parent but *no* span that lacks one (no root). That count should be **0**; anything above means orphaned traces. Then pull a few random sample traces and walk them by eye for missing spans — gaps where work you'd expect to see simply isn't there.
- **Errors captured *when they occur*** — *if* the data contains failed operations, they carry error status and exception detail rather than reporting silent success. **No errors in the window is neither a pass nor a fail** — they may simply not have happened, and you can't confirm error instrumentation from telemetry that contains none. Treat that as untested coverage to note, not a verdict.
- **Conventions** — span and attribute names are present, well-formed, and follow the *current* stable semantic conventions, not deprecated or superseded names (conventions get renamed as they stabilise — e.g. the HTTP attributes were). Look them up rather than assuming: `search_semconv`, `get_semconv_attribute`, plus the org's registry/standard where one exists; flag outdated ones. Span names stay low-cardinality — for HTTP servers that specifically means `http.route` is present, since without it names fall back to high-cardinality full URLs.
- **Registry coverage (when a weaver registry was provided)** — get the list of attributes the service **actually emits** from Honeycomb (`get_dataset_columns` / `find_columns` across the trace, metric, and log datasets that had data sent to them very recently), then let weaver compare that emitted set against the registry so you don't have to eyeball it. weaver checks a JSON sample file of the emitted attributes against the registry — no live stream, no app boot. The full procedure — building the sample file, the exact `weaver registry live-check` invocation and flag guidance, and how to read the verdict from `statistics` — is in **[references/weaver-live-check.md](references/weaver-live-check.md)**. The registry is the standard: attributes emitted-but-undocumented and defined-but-never-emitted are both findings.

### 2. Explore for depth — open-ended judgment

The basic checks confirm the plumbing works; this asks whether the data is actually *useful*. There
is no fixed query list — explore, scoped to the **focus** if one was given, otherwise broadly:

- Open real traces end to end. Following one, can you tell what the app did and why?
- Pick a debugging question someone would actually ask ("which tenant saw these errors?", "what slowed this request?") and try to answer it from the data. Can you?
- Are spans **wide** — carrying the business and high-cardinality context that makes those questions answerable — or just generic defaults?
- **If the repo is provided**, compare what the code *could* surface (domain entities, decisions, identifiers it holds) against what the telemetry carries; flag valuable context that lives in the code but isn't emitted.

### 3. Report

Deliver:

- **A verdict** — **PASS**, **FAIL** (issues found), or **BLOCKED** (nothing arriving to judge). A basic check that fails is a **FAIL**; exploration findings are **gaps** that can still **PASS** unless they defeat the app's core debuggability. Untested coverage (e.g. no errors occurred in the window) is noted, never a FAIL.
- **Reproducible evidence** — a few representative queries the user can re-run, not an exhaustive transcript; lean on the exploration-phase ones that show a real question being answered, plus a sample trace or two. Enough for them to see it themselves rather than take your word.
- **The gaps** — what's missing or weak, expressed as the questions you still can't answer (and, with the repo, the specific context the code holds but doesn't emit). **Return each issue with the query that demonstrates it**, wherever one applies — the not-exhaustive rule above is about proof-of-success, not findings; every reproducible issue gets its query.

When invoked from instrumentation, this report is the input to its fix loop; invoked directly, it is
the user's audit. Either way the job is the same: judge the emitted telemetry against the standard.
