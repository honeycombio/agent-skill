---
name: otel-migration
description: >
  Guide for retrofitting OpenTelemetry into an existing, uninstrumented application.
  Trigger phrases: "migrate existing app to OTel",
  "add OpenTelemetry to existing project", "retrofit OTel into my codebase",
  "thread context through my code", "context propagation",
  "bridge Prometheus metrics to OTel", "logging bridge",
  "migrate logging to OTel", "slog bridge", "logback bridge",
  "verify my instrumentation", "traces are disconnected",
  "orphaned spans", "migrate to OpenTelemetry", "OTel migration plan",
  "how do I sequence an OTel migration", "add tracing to existing code",
  "refactor for context propagation", "Fiber context gotcha",
  "keep existing logging working with OTel", "add OTel without breaking Prometheus",
  "bridge existing metrics", "coexist with existing monitoring",
  or any request about retrofitting OpenTelemetry into an existing application.
  This skill is for migrating existing codebases, NOT greenfield instrumentation (use otel-instrumentation)
  or Beeline-specific migration (use beeline-migration).
metadata:
  version: "1.0.0"
---

# OpenTelemetry Migration for Existing Applications

Guide for retrofitting OpenTelemetry into an existing, uninstrumented application. This covers
the phased migration approach, context propagation refactoring, logging and metrics bridges, and
verification. This is distinct from greenfield OTel setup (see otel-instrumentation skill) and
Beeline-specific migration (see beeline-migration skill).

## When to Use This Skill

Use this skill when the user has an **existing application** that:
- Has no OpenTelemetry instrumentation and needs to add it
- Has existing logging, metrics, or context patterns that must coexist with OTel
- Needs to refactor function signatures to thread trace context through the call stack
- Uses a framework with OTel middleware gotchas (e.g., Fiber, Gin, Express)

For greenfield OTel setup, use the `otel-instrumentation` skill instead.
For Beeline-to-OTel migration, use the `beeline-migration` skill instead.
For understanding *why* to instrument, see the `observability-fundamentals` skill.

## Migration Phases

The migration follows six phases in order. Each phase is independently deployable and verifiable.
Context propagation (Phase 3) is typically ~60% of the effort.

### Phase 1: SDK Initialization and Shutdown

Set up TracerProvider, MeterProvider, and LoggerProvider with OTLP exporters. Wire initialization
early in the application's entry point and shutdown in signal handlers.

**Key guidance:**
- SDK init must happen *before* any application code that might create spans — one of the first
  things in your entry point, before config loading or storage initialization
- Shutdown ordering matters: flush traces, then metrics, then logs. Use a timeout (10-30s)
- If init fails, the application should still work — log the error and continue without telemetry
- For language-specific SDK setup, consult
  `${CLAUDE_PLUGIN_ROOT}/skills/otel-instrumentation/references/sdk-setup-by-language.md`

### Phase 2: HTTP Middleware (Auto-Instrumentation)

Add OTel middleware to your HTTP framework. This gives you automatic spans for every inbound
request with zero code changes to handlers. This is the highest-ROI step.

**Critical:** Different frameworks expose the OTel-enriched context differently. This is the #1
source of silent trace breaks. Consult
`${CLAUDE_PLUGIN_ROOT}/skills/otel-migration/references/framework-middleware.md` for
framework-specific details.

| Framework | How to get OTel context | Common mistake |
|-----------|------------------------|----------------|
| Go net/http | `r.Context()` | N/A (standard) |
| Go Fiber v2 | `c.UserContext()` | Using `c.Context()` (returns fasthttp context without OTel span) |
| Go Gin | `c.Request.Context()` | Using `c` directly |
| Go Echo | `c.Request().Context()` | N/A |
| Python Flask | Automatic (thread-local) | N/A with instrumentation library |
| Python Django | Automatic (thread-local) | N/A with instrumentation library |
| Node.js Express | Automatic (AsyncLocalStorage) | N/A with instrumentation library |
| Java Spring | Automatic (thread-local) | Thread pool context loss |
| .NET ASP.NET Core | Automatic (AsyncLocal) | N/A |
| Ruby Rails | Automatic (thread-local) | N/A with instrumentation library |

### Phase 3: Context Propagation Refactoring

Thread trace context through your call chain from HTTP handlers (or entry points) down to I/O
operations. **This is the hardest phase** — typically ~60% of migration effort.

The difficulty of this phase varies dramatically by language:
- **Go**: Hardest. Requires adding `context.Context` parameter to every function in the call chain.
- **Java**: Moderate. Thread-local context propagates automatically within a thread, but breaks
  across thread pools, CompletableFuture, and reactive streams.
- **Python**: Easier. `contextvars` propagates automatically within a thread. Pain points are
  thread pools and multiprocessing.
- **Node.js**: Easier. `AsyncLocalStorage` propagates through async/await automatically.
  Pain points are old callback-based code.
- **.NET**: Easiest. `Activity` propagates through async/await via `AsyncLocal<T>` automatically.
- **Ruby**: Easier. Thread-local context propagates automatically. Pain with manual thread creation.

For language-specific patterns and code examples, consult
`${CLAUDE_PLUGIN_ROOT}/skills/otel-migration/references/context-propagation-patterns.md`.

### Phase 4: Custom Spans

Add spans to business logic operations that auto-instrumentation doesn't cover. Defer to the
`otel-instrumentation` skill for span creation mechanics. Migration-specific guidance:

1. **Start with I/O boundaries** — database calls, external HTTP calls, cache operations
2. **Then add business logic** — operations that explain *why* time is spent
3. **Add attributes liberally** — every piece of context makes BubbleUp useful during investigations
4. **Record outcomes on spans** — result status, error count, duration as attributes

For attribute naming and span creation patterns, consult
`${CLAUDE_PLUGIN_ROOT}/skills/otel-instrumentation/references/custom-instrumentation.md`.

### Phase 5: Logging Migration

Replace or bridge your existing logging library into OTel so logs correlate with traces.

**Key guidance:**
- You almost certainly want logs going to both stderr (local debugging) AND OTel (trace correlation).
  This requires a multi-handler/fan-out pattern.
- OTel log bridges work with structured logging (key-value pairs). If your existing logging uses
  printf-style format strings, convert to structured format first.
- Converting from printf-style to structured logging is tedious but mechanical — a good candidate
  for automated refactoring.

For language-specific logging bridges and the multi-handler pattern, consult
`${CLAUDE_PLUGIN_ROOT}/skills/otel-migration/references/bridge-libraries.md`.

### Phase 6: Metrics Bridge

If you already have Prometheus metrics (or another metrics library), bridge them to OTel rather
than rewriting.

**Key guidance:**
- Prometheus bridge reads from the existing registry and produces OTel metrics — existing
  `prometheus.NewCounterVec(...)` calls continue unchanged
- Keep the Prometheus `/metrics` endpoint if you have existing scrapers. The bridge adds OTLP
  export *in addition to* scraping.
- If you want to eventually remove the Prometheus dependency, plan a separate migration later.
  The bridge buys you time.

For language-specific metrics bridges, consult
`${CLAUDE_PLUGIN_ROOT}/skills/otel-migration/references/bridge-libraries.md`.

## Verification

After each phase, verify that instrumentation is correct and complete. Consult
`${CLAUDE_PLUGIN_ROOT}/skills/otel-migration/references/verification-checklist.md` for the
full checklist and query patterns.

To verify locally without a Honeycomb account, use the bundled collector script to capture
spans as debug output and NDJSON. Consult
`${CLAUDE_PLUGIN_ROOT}/skills/otel-instrumentation/references/local-collector-debug-test.md` for usage, and
`${CLAUDE_PLUGIN_ROOT}/scripts/start-collector.sh` for the full script.

For Honeycomb-specific verification queries, also consult the `query-patterns` skill.

## Common Pitfalls

For a catalog of common mistakes and how to avoid them, consult
`${CLAUDE_PLUGIN_ROOT}/skills/otel-migration/references/migration-pitfalls.md`.

## Real-World Calibration

For reference, a real migration of Gatus (~30k LOC Go, Fiber v2, SQLite/Postgres, Prometheus):
- **Files changed:** ~45, **Lines:** +840/-645
- **Effort breakdown:** Context propagation ~60%, Custom spans ~15%, Logging migration ~15%, Everything else ~10%
- **Bugs encountered:** Fiber `c.Context()` vs `c.UserContext()`, printf-style slog format strings,
  missing `span.End()` calls, goroutine context reuse
