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

## Pattern: Recording Events Within a Span

For things that happen at a point in time within a span, use span events:

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
a low-cardinality, greppable identifier that connects dashboards directly to code.

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
