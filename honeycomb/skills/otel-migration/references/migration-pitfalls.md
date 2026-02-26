# Migration Pitfalls

Common mistakes encountered during OTel migration and how to avoid them. These are ordered
by how frequently they occur in practice.

## 1. Silent Context Breaks

**Affects:** All languages
**Symptom:** Traces appear as disconnected root spans instead of a connected tree
**Cause:** Context propagation breaks at one layer, so all spans below become root spans

There is no error, no warning. Your code works fine, you just get disconnected traces.
Always verify with a trace waterfall view after each migration phase.

**How to detect:** Query for spans where `trace.parent_id` does not exist. If most of your
spans are root spans, context is breaking somewhere.

## 2. Wrong Framework Context Accessor

**Affects:** Go (Fiber, Gin), and any framework with a context wrapper
**Symptom:** Orphaned spans, disconnected traces
**Cause:** Using the framework's internal context instead of the OTel-enriched context

The most common instance is Fiber v2:

```go
// WRONG — returns fasthttp context without OTel span
ctx := c.Context()

// RIGHT — returns context with OTel span
ctx := c.UserContext()
```

This compiles, runs, and returns correct results. Traces just silently break. See
framework-middleware.md for the correct accessor for each framework.

## 3. Reusing Parent Context in Loops

**Affects:** All languages, but especially Go
**Symptom:** All loop iterations appear under a single never-ending span, or all share
the same parent without their own spans

```go
// WRONG — all iterations share the loop's parent span
for _, item := range items {
    processItem(ctx, item)
}

// RIGHT — each iteration gets its own span
for _, item := range items {
    itemCtx, span := tracer.Start(ctx, "process item")
    processItem(itemCtx, item)
    span.End()
}
```

**Python equivalent:**
```python
# WRONG
for item in items:
    process_item(item)

# RIGHT
for item in items:
    with tracer.start_as_current_span("process item"):
        process_item(item)
```

## 4. Forgetting span.End()

**Affects:** Go, Java, Node.js (languages without context-manager-based span lifecycle)
**Symptom:** Spans silently disappear — never exported
**Cause:** Every `tracer.Start()` must have a matching `span.End()`

```go
// ALWAYS use defer immediately after Start
ctx, span := tracer.Start(ctx, "operation")
defer span.End()
```

```java
// ALWAYS use try-finally or try-with-resources
Span span = tracer.spanBuilder("operation").startSpan();
try (Scope scope = span.makeCurrent()) {
    // work
} finally {
    span.end();
}
```

Python and Ruby context managers handle this automatically:
```python
with tracer.start_as_current_span("operation"):
    # span.end() called automatically
```

## 5. Printf-Style Logging After Migration

**Affects:** Go (slog migration), Python, any language converting to structured logging
**Symptom:** Malformed log entries, lost structured data

```go
// WRONG — format string becomes the message, structured fields lost
slog.Info(fmt.Sprintf("found %d users", count))

// WRONG — %d is literal text in the message
slog.Info("found %d users", "count", count)

// RIGHT — structured key-value pairs
slog.Info("found users", "count", count)
```

This is tedious but mechanical to fix. Search for `fmt.Sprintf` inside `slog.` calls,
or `%` format strings in log messages.

## 6. Not Propagating Context to HTTP Client Calls

**Affects:** All languages
**Symptom:** Outbound HTTP calls don't appear in the trace, W3C trace headers not propagated
**Cause:** Creating HTTP requests without trace context

```go
// WRONG — no context, no trace propagation
req, _ := http.NewRequest("GET", url, nil)

// RIGHT — context carries trace info, W3C headers injected automatically
req, _ := http.NewRequestWithContext(ctx, "GET", url, nil)
```

```python
# With requests instrumentation installed, context propagates automatically
# But if making raw urllib calls:
import urllib.request
# WRONG — no context propagation
urllib.request.urlopen(url)
```

Most language SDKs auto-instrument HTTP clients (Go `net/http`, Python `requests`, Node.js
`http`/`undici`, Java `HttpClient`). But only if the auto-instrumentation library is installed
and the request is made with context.

## 7. Thread Pool Context Loss

**Affects:** Java, Python, Ruby (thread-local context languages)
**Symptom:** Spans created in thread pool workers are orphaned root spans
**Cause:** Thread-local context doesn't propagate to new threads automatically

```java
// WRONG — context lost
executor.submit(() -> doWork());

// RIGHT — wrap with current context
executor.submit(Context.current().wrap(() -> doWork()));
```

```python
# WRONG — context lost
executor.submit(do_work)

# RIGHT — copy context
ctx = contextvars.copy_context()
executor.submit(ctx.run, do_work)
```

See context-propagation-patterns.md for language-specific details.

## 8. Testing with Noop Providers

**Affects:** All languages
**Symptom:** Tests pass but don't verify instrumentation
**Cause:** Without a registered provider, `otel.Tracer()` returns a noop tracer

`tracer.Start(ctx, "...")` returns a valid but empty span and context. Tests work, but
they don't verify that spans are created correctly.

If you want to test instrumentation:
- Register an in-memory exporter in test setup
- Assert on exported spans after the operation
- Check span names, attributes, and parent-child relationships

If you just want tests to pass without verifying instrumentation, the noop behavior is fine.

## 9. Shutdown Ordering and Timeout

**Affects:** All languages
**Symptom:** Missing tail-end telemetry (last few seconds before shutdown)
**Cause:** Process exits before the OTel SDK flushes pending spans/metrics/logs

Shutdown must:
1. Flush traces first (TracerProvider.Shutdown)
2. Then metrics (MeterProvider.Shutdown)
3. Then logs (LoggerProvider.Shutdown)
4. Use a timeout (10-30s) — without it, a hung exporter blocks process exit

```go
ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
defer cancel()
// Shutdown in order
tracerProvider.Shutdown(ctx)
meterProvider.Shutdown(ctx)
loggerProvider.Shutdown(ctx)
```

## 10. Attribute Type Mismatches

**Affects:** All languages
**Symptom:** Attributes appear with unexpected values or are silently dropped
**Cause:** Passing wrong types to attribute setters

OTel attributes are typed. Common mistakes:
- Passing an integer where a string is expected (or vice versa)
- Using `attribute.String("count", "5")` when you mean `attribute.Int("count", 5)`
- Inconsistent types for the same attribute name across different spans (your backend may
  reject or mishandle this)

Pick a type for each attribute name and use it consistently across your codebase.
