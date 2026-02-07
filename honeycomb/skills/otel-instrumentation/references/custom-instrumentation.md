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

## Attribute Naming Best Practices

- Use dot-separated namespaces: `user.id`, `order.total`, `cache.hit`
- Follow OTel semantic conventions where they exist
- Create your own namespace for custom attributes: `app.`, `mycompany.`
- Keep attribute values low-cardinality where possible (for GROUP BY)
- High-cardinality is fine for debugging (trace IDs, user IDs, order IDs)
