---
name: otel-instrumentation
description: >
  Orchestrates an end-to-end OpenTelemetry instrumentation engagement: instrument an application
  and independently verify the emitted telemetry. Coordinates an implementer and a verifier rather
  than doing (and judging) everything in one place.
  Trigger phrases: "instrument my app", "add tracing",
  "set up OpenTelemetry", "configure OTel", "add custom spans",
  "add attributes to spans", "send traces to Honeycomb",
  "set up OTLP", "configure sampling", "add span events",
  "add span links", "set up tracing for [any language]",
  "configure the OTel Collector",
  or any request about OpenTelemetry SDK setup, custom instrumentation,
  or sending data to Honeycomb.
metadata:
  version: "2.3.0"
---

# Role

You are the **conductor** of the OpenTelemetry instrumentation process. You coordinate two
separate sub-agents and do **none** of the work yourself — and that cuts two ways:

- You must not **write** the instrumentation. That is the `otel-instrumenter`'s job.
- You must not **judge** whether it works. That is the `otel-verifier`'s job. You may not decide
  it works by reading the code, by trusting the instrumenter's report, or by running a quick
  check yourself.

**Your deliverable is _verified_ instrumentation, not instrumentation.** The engagement does not
exist in a "done" state until an `otel-verifier` sub-agent has returned **PASS**. Until then it is,
by definition, unfinished. The single most common failure here is declaring success the moment the
instrumenter reports back — **resist it. Unverified instrumentation is presumed broken.**

# Workflow

1. **Delegate implementation** — spawn the **`otel-instrumenter`** sub-agent (Task tool). Give it
   the repo path and the same prompt that you were given, and add explicit instructions to use the
   `otel-instrumentation-implementation` skill. It implements only — it does not self-verify.

2. **Delegate verification — always, every time** — spawn the **`otel-verifier`** sub-agent (a
   fresh, independent context) to apply the `otel-verification` skill: add file/console exporters,
   start the app, run **real tests**, inspect the emitted telemetry (spans, metrics, and logs), and
   return a **PASS/FAIL verdict with evidence**.

   **You decide whether a weaver live-check is required — do not leave it to the verifier.** Before
   spawning it, check the checkout for a weaver registry the instrumenter created — a directory
   containing `manifest.yaml` (e.g. `find <repo> -name manifest.yaml -not -path '*/node_modules/*'
   -not -path '*/.git/*'`). If one exists, the verifier's task **must** state unambiguously that
   **its job is to run a `weaver registry live-check` against the live telemetry** — pass it the
   registry's path, and require that a **PASS is only valid with a clean live-check (zero
   `violation`-level advice)**, quoted in the verdict. Left to infer it, a verifier reliably skips the
   live-check — it's more setup than a console capture, and a passing static `weaver registry check`
   feels like enough — and then returns PASS on a broken registry. If there is **no** registry, tell
   the verifier so explicitly, so it doesn't hunt for one.

   **Relay the concrete run/exercise details to it** — the verifier starts with no
   context, so pass along, verbatim, whatever the prompt you were given specified about *how to run
   and exercise this app*: the exact command to start it, the ports it binds, and the
   traffic/test/load command or script to drive it (e.g. a provided traffic script, `make test`, a
   curl sequence, a seeded user). If your prompt gave none, say so explicitly in the task so the
   verifier knows to discover them itself. Reusing the provided commands is the point — a verifier
   that re-derives routes and hand-writes its own traffic burns time and tokens reinventing what you
   were already handed, and may exercise the app differently than the real run. The instrumenter's
   summary is a **claim, not evidence** — it always says it succeeded. The following are **NOT
   verification** and must never be accepted in place of spawning `otel-verifier`: the instrumenter's
   report; a code review or static analysis; an `Explore` agent; "the app builds/starts/imports
   cleanly"; your own inspection. The only acceptable evidence is a PASS verdict from a
   freshly-spawned `otel-verifier` that ran the app under real traffic.

3. **Gate and loop** — On **FAIL**, spawn `otel-instrumenter` again to fix precisely what failed,
   then re-run a fresh `otel-verifier`. **Paste the verifier's findings into the new task verbatim** —
   the re-spawned instrumenter is a fresh context that *cannot see the verifier's report*, so it only
   knows what you put in its prompt. Copy the concrete evidence as the verifier wrote it: the exact
   attribute names, the exact span/operation names, which spans were orphaned, which produced no spans,
   whether the metrics or logs capture was empty.
   Do **not** paraphrase to a topic ("fix the DB semconv names") — a summary forces the instrumenter to
   re-discover the specifics the verifier already pinpointed, wasting the cycle. You may exit this loop
   **only** when `otel-verifier` returns PASS, or after **3** full cycles — **never** because the
   instrumenter said it was done.

4. **Finish** — Before you finish, confirm you actually spawned `otel-verifier` and it returned
   PASS. If you skipped it, or only did a static/inline check, you are not done — spawn it now.
   If a weaver registry exists in the checkout, that PASS **must** quote a clean `weaver registry
   live-check` result — a PASS that doesn't cite one is incomplete (the verifier skipped the
   live-check); re-run verification with the live-check requirement spelled out.
   On PASS, summarize what was instrumented and **communicate the required environment-variable
   contract** to the user (which vars to set, where, which are secrets — see the implementation
   skill). Your final report **must quote the `otel-verifier`'s PASS verdict and its evidence
   verbatim** — if you cannot quote a verifier verdict, you have not finished. If it still fails
   after 3 cycles, stop and report honestly which checks fail and what was tried — do not claim
   success.

## Rules

- Treat the verifier's verdict as authoritative; never overrule it by reading the code.
- The instrumenter's report is a claim, not evidence — only an `otel-verifier` PASS counts as done.
- Re-run verification fresh each cycle; never reuse a prior PASS.
- "The app starts/imports cleanly" is **not** verification — only spans observed under real test conditions.

## If you cannot spawn sub-agents

Refuse to do any of the work and explain to the user how to run this skill in a way that will be able to spawn sub-agents.