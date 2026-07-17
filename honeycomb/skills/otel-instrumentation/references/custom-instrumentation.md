# Custom Instrumentation Patterns

Detailed patterns for adding custom instrumentation beyond auto-instrumentation.

## When to Add Custom Instrumentation

Auto-instrumentation covers:
- HTTP server/client requests
- Database queries
- gRPC calls
- Message queue operations

Add custom instrumentation for:
- Business logic (checkout flow, payment processing)
- Cache operations
- Internal function calls that matter
- Custom attributes with business context

## Pattern: Adding Context to Auto-Instrumented Spans

The most impactful custom instrumentation. No new spans needed — just add
attributes to existing spans.

### Go
```go
func handleCheckout(w http.ResponseWriter, r *http.Request) {
    span := trace.SpanFromContext(r.Context())
    span.SetAttributes(
        attribute.String("user.id", getUserID(r)),
        attribute.Float64("cart.total", cart.Total()),
        attribute.Int("cart.items", cart.ItemCount()),
        attribute.String("payment.method", cart.PaymentMethod()),
    )
    // ... rest of handler
}
```

### Python
```python
@app.route("/checkout", methods=["POST"])
def handle_checkout():
    span = trace.get_current_span()
    span.set_attribute("user.id", get_user_id())
    span.set_attribute("cart.total", cart.total)
    span.set_attribute("cart.items", cart.item_count)
    span.set_attribute("payment.method", cart.payment_method)
    # ... rest of handler
```

### Node.js
```javascript
app.post("/checkout", (req, res) => {
    const span = trace.getActiveSpan();
    span.setAttribute("user.id", req.user.id);
    span.setAttribute("cart.total", cart.total);
    span.setAttribute("cart.items", cart.itemCount);
    span.setAttribute("payment.method", cart.paymentMethod);
    // ... rest of handler
});
```

## Pattern: Wrapping Business Logic in Custom Spans

Create spans around operations you want to see in the trace waterfall.

> The `RecordError`/`record_exception` calls in the compatibility snippets below show the
> legacy span-event exception API. For new code, prefer the **Exception Events with the Logs API**
> pattern below; retain the legacy call only when required by an existing SDK, query, or migration.

### Go
```go
func processPayment(ctx context.Context, order *Order) error {
    tracer := otel.Tracer("checkout-service")
    ctx, span := tracer.Start(ctx, "process-payment")
    defer span.End()

    span.SetAttributes(
        attribute.String("order.id", order.ID),
        attribute.Float64("order.total", order.Total),
        attribute.String("payment.provider", order.PaymentProvider),
    )

    result, err := paymentGateway.Charge(ctx, order)
    if err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, err.Error())
        return err
    }

    span.SetAttributes(attribute.String("payment.transaction_id", result.TransactionID))
    return nil
}
```

### Python
```python
def process_payment(order):
    tracer = trace.get_tracer("checkout-service")
    with tracer.start_as_current_span("process-payment") as span:
        span.set_attribute("order.id", order.id)
        span.set_attribute("order.total", order.total)
        span.set_attribute("payment.provider", order.payment_provider)

        try:
            result = payment_gateway.charge(order)
            span.set_attribute("payment.transaction_id", result.transaction_id)
        except Exception as e:
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, str(e))
            raise
```

## Pattern: Exception Events with the Logs API

For new exception instrumentation, emit a Logs API record while the relevant span is active.
Use the standard `exception.*` fields, ERROR severity, and `event.name="exception"`. Set span
status and low-cardinality span dimensions separately so humans can aggregate operation failures
without copying stack traces onto spans.

```text
log event (while span is active):
  event.name = "exception"
  body = "exception"
  severity = ERROR
  exception.type, exception.message, exception.stacktrace, exception.escaped

containing span:
  status = ERROR
  error = true
  exception.slug = "err-payment-provider-timeout"  # static, optional, low-cardinality
```

Honeycomb correlates the log to the active trace and renders it as a `span_event` annotation.
The event row carries `trace.trace_id` and `trace.parent_id`, but Logs API exception fields are
not hoisted onto the containing span. Query the event row for the diagnostic payload, then use
its `trace.trace_id` with `get_trace(show_events=true)` to inspect the surrounding trace.

The legacy `record_exception` / `RecordError` APIs remain useful for compatibility and existing
instrumentation. Do not assume their `name=exception` shape applies to Logs API events: Logs API
uses `event.name=exception` (and often `body=exception`) with `meta.signal_type=log`.

**SDK implementation note:** use the language's supported Logs API or logging bridge, and verify
that the record carries the active context. Python's current app-facing path is the stdlib
`logging` bridge; Go passes the active context explicitly to `logger.Emit(ctx, record)`; Node
requires an installed context manager and an explicit active context; Java attaches context from
`span.makeCurrent()`. Do not emit the exception after the span scope closes.

### Optional compatibility pattern: exception-promoting LogRecordProcessor

Honeycomb's historical span-event path can promote exception fields onto the parent span. A
trace-correlated Logs API exception does not receive that promotion automatically. If an existing
span-oriented query surface must be preserved, implement a custom **LogRecordProcessor**, registered
before the batch/export processor:

```text
on_emit(log_record, resolved_context):
    if log_record.event_name != "exception":
        return

    span = span_from_context(resolved_context)
    if span is absent or not recording:
        return

    # Promote only fields needed by span-level queries.
    span.set_attribute("error", true)
    span.set_attribute("error.type", log_record["exception.type"])
    span.set_attribute("exception.type", log_record["exception.type"])
    if log_record has "exception.slug":
        span.set_attribute("exception.slug", log_record["exception.slug"])
    if configured for legacy compatibility:
        span.set_attribute("exception.message", log_record["exception.message"])
        span.set_attribute("exception.stacktrace", log_record["exception.stacktrace"])

    # Leave the log record unchanged; it remains the diagnostic source of truth.
```

The processor should be synchronous and must run while the span is still mutable. It should no-op
when there is no valid recording span, preserve the original log record, and never invent fields
that were not emitted. Treat `exception.message` and especially `exception.stacktrace` promotion
as an explicit compatibility option because they are high-cardinality and potentially large.

This is not a standalone `SpanProcessor`: span processors do not receive log records. A span
processor could only participate through a separate shared registry, which adds races, cleanup,
and lifecycle complexity. The exact processor and context APIs are language-specific:

- Go: use the explicit context passed to `logger.Emit(ctx, record)`.
- Java: use the resolved log context; do not reconstruct context after async queueing.
- Node.js: ensure the context manager is installed and use the record's explicit context.
- Python: preserve the active context through the stdlib logging bridge and Logs SDK processor.

Use this only as a migration aid. Agents should still query Logs API exception rows for full
`exception.*` diagnostics and treat promoted span fields as instrumentation-dependent.

## Pattern: Recording Events Within a Span

For non-exception milestones and state changes, use the Logs API for new point-in-time events
when the language SDK supports it. Keep legacy span events where the SDK has no usable Logs API
or compatibility requires them:

```python
with tracer.start_as_current_span("process-order") as span:
    span.add_event("validating_order", {"order.id": order.id})

    if not validate(order):
        span.add_event("validation_failed", {"reason": "invalid_address"})
        raise ValidationError()

    span.add_event("charging_payment", {"amount": order.total})
    charge(order)

    span.add_event("order_completed", {"order.id": order.id})
```

## Pattern: Linking Related Traces

When an async job is triggered by a request, link them:

```python
# In the message consumer:
from opentelemetry.trace import Link

def process_message(message):
    # Extract the producing span's context from the message
    producer_context = extract_context(message.headers)

    with tracer.start_as_current_span(
        "process-message",
        links=[Link(producer_context, {"link.reason": "triggered_by"})],
    ) as span:
        span.set_attribute("message.id", message.id)
        # ... process message
```

## Pattern: Timing Attributes on Parent Spans

Put important sub-operation durations as attributes on the parent span instead of
creating child spans for everything.

> **Anti-pattern warning:** Wrapping absolutely everything in its own span is the most
> common failure mode when engineers first get access to tracing tools. You have to
> design the structure of your data for the way you want to query it.

Child spans are helpful for waterfall visualization of a single request, but they're
difficult to query across *all* requests. Timing attributes on a single span are
easier to query and work directly with tools like BubbleUp — which can immediately
surface "that group of requests was slow because authentication took 10 seconds."

### Go
```go
func handleRequest(w http.ResponseWriter, r *http.Request) {
    span := trace.SpanFromContext(r.Context())

    // Time authentication
    authStart := time.Now()
    user, err := authenticate(r)
    authDur := time.Since(authStart)
    span.SetAttributes(attribute.Float64("auth.duration_ms", float64(authDur.Milliseconds())))

    // Time payload parsing
    parseStart := time.Now()
    payload, err := parsePayload(r)
    parseDur := time.Since(parseStart)
    span.SetAttributes(attribute.Float64("payload_parse.duration_ms", float64(parseDur.Milliseconds())))

    // ... rest of handler
}
```

### Python
```python
@app.route("/api/resource", methods=["POST"])
def handle_request():
    span = trace.get_current_span()

    # Time authentication
    auth_start = time.monotonic()
    user = authenticate(request)
    span.set_attribute("auth.duration_ms", (time.monotonic() - auth_start) * 1000)

    # Time payload parsing
    parse_start = time.monotonic()
    payload = parse_payload(request)
    span.set_attribute("payload_parse.duration_ms", (time.monotonic() - parse_start) * 1000)

    # ... rest of handler
```

### Node.js
```javascript
app.post("/api/resource", async (req, res) => {
    const span = trace.getActiveSpan();

    // Time authentication
    const authStart = performance.now();
    const user = await authenticate(req);
    span.setAttribute("auth.duration_ms", performance.now() - authStart);

    // Time payload parsing
    const parseStart = performance.now();
    const payload = await parsePayload(req);
    span.setAttribute("payload_parse.duration_ms", performance.now() - parseStart);

    // ... rest of handler
});
```

**When to use this pattern:**
- The operation is important to understanding request latency
- You want to GROUP BY or BubbleUp on the timing alongside other parent span attributes
- The alternative (a child span) would require JOINs for cross-request analysis

**When a child span is still better:**
- The operation makes downstream calls you also want to trace
- You need to see the operation in the waterfall view for single-request debugging
- The operation has its own rich set of attributes worth capturing

## Pattern: Exception Slugs

Tag each error throw site with a unique static string (`exception.slug`). This creates
a low-cardinality, greppable identifier that connects dashboards directly to code. Keep this
attribute on the operation span even when full exception details are emitted as a Logs API event.
The legacy `RecordError`/`record_exception` calls shown in this section are compatibility examples;
they are not a requirement for new Logs API instrumentation.

### Go
```go
func processPayment(ctx context.Context, order *Order) error {
    span := trace.SpanFromContext(ctx)

    result, err := stripe.Charge(ctx, order)
    if err != nil {
        // Static string — not dynamically generated
        // Consider enforcing this with custom lint rules
        span.SetAttributes(
            attribute.String("exception.slug", "err-stripe-charge-failed"),
            attribute.Bool("error", true),
        )
        span.RecordError(err)
        span.SetStatus(codes.Error, err.Error())
        return err
    }

    if !result.Approved {
        span.SetAttributes(
            attribute.String("exception.slug", "err-payment-declined"),
            attribute.Bool("error", true),
        )
        return ErrPaymentDeclined
    }

    return nil
}
```

### Python
```python
def process_payment(order):
    span = trace.get_current_span()
    try:
        result = stripe.charge(order)
    except stripe.CardError as e:
        span.set_attribute("exception.slug", "err-stripe-card-error")
        span.set_attribute("error", True)
        span.record_exception(e)
        span.set_status(StatusCode.ERROR, str(e))
        raise
    except stripe.APIError as e:
        span.set_attribute("exception.slug", "err-stripe-api-unavailable")
        span.set_attribute("error", True)
        span.record_exception(e)
        span.set_status(StatusCode.ERROR, str(e))
        raise
```

### Node.js
```javascript
async function processPayment(order) {
    const span = trace.getActiveSpan();
    try {
        const result = await stripe.charges.create(order);
        if (!result.approved) {
            span.setAttribute("exception.slug", "err-payment-declined");
            span.setAttribute("error", true);
            throw new PaymentDeclinedError();
        }
    } catch (err) {
        if (!span.attributes?.["exception.slug"]) {
            span.setAttribute("exception.slug", "err-stripe-call-failed");
        }
        span.setAttribute("error", true);
        span.recordException(err);
        span.setStatus({ code: SpanStatusCode.ERROR, message: err.message });
        throw err;
    }
}
```

**Why this pattern matters:**
- **Greppable:** Search your codebase for the exact slug string to find the throw site
- **Low-cardinality GROUP BY:** Safe to use in `GROUP BY exception.slug` queries
- **Gap detection:** Any failed request *without* an `exception.slug` reveals places
  where your error handling could be improved — it's easy to find errors you didn't
  anticipate

**Query — find unhandled errors (missing slugs):**
```
VISUALIZE COUNT
WHERE error = true AND exception.slug = NULL
GROUP BY http.route
```

## Pattern: Async Request Summaries

Roll up child operation statistics onto the parent span to identify outlier requests
without needing to count child spans manually.

### Go
```go
type RequestStats struct {
    mu             sync.Mutex
    pgQueryCount   int
    pgQueryDurMs   float64
    httpReqCount   int
    httpReqDurMs   float64
}

func (s *RequestStats) RecordPgQuery(dur time.Duration) {
    s.mu.Lock()
    defer s.mu.Unlock()
    s.pgQueryCount++
    s.pgQueryDurMs += float64(dur.Milliseconds())
}

func (s *RequestStats) RecordHTTPReq(dur time.Duration) {
    s.mu.Lock()
    defer s.mu.Unlock()
    s.httpReqCount++
    s.httpReqDurMs += float64(dur.Milliseconds())
}

func (s *RequestStats) SetOnSpan(span trace.Span) {
    s.mu.Lock()
    defer s.mu.Unlock()
    span.SetAttributes(
        attribute.Int("stats.postgres_query_count", s.pgQueryCount),
        attribute.Float64("stats.postgres_query_duration_ms", s.pgQueryDurMs),
        attribute.Int("stats.http_requests_count", s.httpReqCount),
        attribute.Float64("stats.http_requests_duration_ms", s.httpReqDurMs),
    )
}
```

### Python
```python
class RequestStats:
    def __init__(self):
        self.pg_query_count = 0
        self.pg_query_duration_ms = 0.0
        self.http_req_count = 0
        self.http_req_duration_ms = 0.0

    def record_pg_query(self, duration_ms):
        self.pg_query_count += 1
        self.pg_query_duration_ms += duration_ms

    def record_http_request(self, duration_ms):
        self.http_req_count += 1
        self.http_req_duration_ms += duration_ms

    def set_on_span(self, span):
        span.set_attribute("stats.postgres_query_count", self.pg_query_count)
        span.set_attribute("stats.postgres_query_duration_ms", self.pg_query_duration_ms)
        span.set_attribute("stats.http_requests_count", self.http_req_count)
        span.set_attribute("stats.http_requests_duration_ms", self.http_req_duration_ms)

# Usage in a request handler:
@app.route("/api/resource")
def handle():
    stats = RequestStats()
    # Pass stats to DB and HTTP client wrappers...
    # At end of request:
    stats.set_on_span(trace.get_current_span())
```

**Why this pattern matters:**
- A request that makes 742 database queries is almost certainly doing something wrong
- Without summary stats, these outliers are invisible — you'd need to count child spans
  per trace manually
- HEATMAP of `stats.postgres_query_count` instantly reveals bimodal distributions
  and outliers

**Query — database queries per request:**
```
VISUALIZE HEATMAP(stats.postgres_query_count)
WHERE service.name = "api-service"
```

## Attribute Naming Best Practices

- Use dot-separated namespaces: `user.id`, `order.total`, `cache.hit`
- Follow OTel semantic conventions where they exist
- Create your own namespace for custom attributes: `app.`, `mycompany.`
- Keep attribute values low-cardinality where possible (for GROUP BY)
- High-cardinality is fine for debugging (trace IDs, user IDs, order IDs)
