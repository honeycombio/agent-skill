# Trace Design Patterns for Non-Request/Response Architectures

Most tracing models fit request/response architectures well: a client sends a request,
the service does work, and the trace captures the full waterfall. The further your
architecture drifts from request/response, the more intentional your trace design
needs to be.

This reference covers patterns for streaming, async jobs, long-running ETL, and
serverless — drawn from Chapter 7 of *Observability Engineering* (2nd edition).

## Streaming (Kafka / Queues / Message Buses)

Stream processing is the second most common architecture after request/response.
Tracing it is tricky because:
1. The smallest instrumentable "unit of work" isn't always the most useful unit to optimize
2. The questions you want to answer often involve trace *shape* (stage dwell times,
   success/failure ratios) rather than individual spans

### Context Propagation

Serialize trace context into the message envelope when publishing. Extract it when
consuming. For Kafka and similar systems, message envelopes make this straightforward.

```
Producer:
  orders-api creates span "messaging.publish" (kind: PRODUCER)
  → attributes: messaging.system, messaging.destination, message.id, order.id, customer.id
  → context serialized into message envelope of OrderPlaced event

Consumer:
  payment-svc extracts context from envelope
  → creates span "messaging.process" (kind: CONSUMER)
  → linked to producer span via Span Links (not as direct child)
  → when producing new messages, repeats the cycle
```

### Correlation IDs

Store a unique identifier (e.g., `order.transaction_id`) and propagate it through the
entire pipeline. This ties all traces together directly without walking the tree in reverse.

This shifts from one trace with a single root and many children into a **timeline of
traces** linked by a shared correlation ID. You can pull all relevant spans into a
result set by filtering on the correlation ID.

### Fleet-Level Alerting with Metrics

Span-level tracing provides excellent visibility into a single message's journey, but
generalizing across the fleet requires metrics:

- **Counters per stage**: Emit success/failure counts with attributes mirroring span data
  (but at lower cardinality — no transaction IDs on metric points)
- **Histograms for dwell time**: Track time from publish to process per stage/type/region
- **Exemplars**: Annotate histogram data points with trace and span IDs to link outlier
  metrics directly to the traces that produced them
- **Alert on ratios**: `failed_total / processed_total` per stage, with histograms for
  proactive alerting on unusual queue behavior

### Example Pipeline

```
orders-api (produces OrderPlaced)
  → topic: orders.events
      ├─ payment-svc (consumes OrderPlaced → produces PaymentAuthorized/Declined)
      ├─ inventory-svc (consumes PaymentAuthorized → produces InventoryReserved)
      ├─ shipping-svc (consumes InventoryReserved → produces ShipmentCreated)
      └─ reconcile-job (nightly batch over events store)
```

Each stage: extract context → create consumer span → link to producer → add business
attributes → produce new messages with propagated context.

## Async Jobs (Fan-Out / Fan-In)

For scatter-gather patterns like video processing or parallel task execution.

### Pattern

```
POST /render → orchestrator (ROOT span)
  ├─ publish task.transcode    ─→ worker processes
  ├─ publish task.thumbnail    ─→ worker processes
  └─ publish task.caption      ─→ worker processes
workers process → orchestrator joins when N succeed or deadline
```

The root span is the entrypoint (the POST). Child processes link back via parent/child
or producer/consumer relationships. The root span should contain **links to each child
process** and a **final summarization span** that rolls up results.

### Avoiding the "Million Children" Hazard

Fan-out patterns can produce traces with enormous numbers of children, making them
expensive to store and unusable to visualize. Strategies:

- Use Span Links instead of parent/child for loosely coupled work
- Add summarization attributes on the root span (`tasks.total`, `tasks.succeeded`,
  `tasks.failed`, `tasks.duration_ms`)
- Alert on the entrypoint span or specific child tasks depending on ownership

### Alerting

Metrics may be less useful than spans here because there's no shared infrastructure to
optimize beyond network links. Focus alerting on the orchestrator span.

## Long-Running Jobs (ETL / Batch Processing)

Jobs that run for hours or days (e.g., nightly ETL compiling inventory from thousands
of suppliers) don't fit the traditional trace model.

### The Problem

A single root span lasting hours creates issues:
- Most tracing backends don't handle updates to existing spans
- A trace with thousands of child spans per stage is expensive and hard to visualize
- The "million children trace" hazard applies here too

### Recommended Pattern: Separate Traces Per Stage

Model each stage as its own trace, related by links and correlation identifiers:

```
scheduler → [job.run nightly_etl] (correlation: job_id=abc123)
              ├─ etl.extract   (own trace, linked by job_id)
              ├─ etl.transform (own trace, linked by job_id, may run for hours)
              ├─ etl.load      (own trace, linked by job_id)
              └─ report.write  (own trace, linked by job_id)
```

Correlate all stages by querying on the shared `job_id`.

### Alternative: Wide-Event Summarization

If your primary goal is a safety net rather than fine-grained optimization, emit a
single **summarization span** (or log event) at job completion with rich metadata:

- Hundreds of attributes capturing what succeeded, what failed, and why
- Stage durations, record counts, error summaries
- Useful for tracking changes over time without the overhead of a well-formed trace

### Intermediate Visibility

Use metrics or logs for intermediate status reports you can monitor while the job runs,
without breaking the span/trace data model. As long as trace context is preserved through
child processes, metrics associate back to their underlying traces.

### Which Approach to Choose

Ask yourself: are you checking a box for requirements, or trying to understand and
optimize individual job performance?

- **Safety net**: Wide-event summarization approach
- **Performance optimization**: Separate traces per stage with links
- **Both**: Combine both approaches — separate traces for stages plus a summarization
  event at completion

## Serverless (Lambda / Cloud Functions)

Serverless constraints change the tradeoffs for instrumentation.

### Favor Custom Over Auto-Instrumentation

Resource constraints in serverless environments mean auto-instrumentation's overhead
(cold-start time, memory) may not be worth the generic spans it produces. A single
well-designed span per invocation, rich with attributes, often beats a sprawling hierarchy.

### Design Pattern

```
Lambda invocation → single span with rich attributes:
  - function.name, function.version
  - trigger.type (API Gateway, SQS, S3, etc.)
  - invocation.id (for post-hoc correlation)
  - Business context attributes
  - Duration breakdowns as timing attributes
  - Error details with exception.slug
```

### Stateless Tracing Strategy (AWS-Specific)

An advanced pattern for performance-critical Lambda functions:
1. Emit lightweight events from the function runtime
2. A stateful OpenTelemetry Collector (in an extension layer) assembles events into spans
3. Reduces statefulness requirements in the function, minimizing cold-start impact

This trades simpler function code for more complex Collector-side logic.

### Cross-Invocation Correlation

Different serverless platforms offer different hooks for post-execution telemetry, often
not in native OTel formats. Correlate data post-hoc through:
- A shared invocation ID or UUID
- Telemetry pipelines that normalize and forward events together
- Federated queries across multiple data stores

### Key Principles

- **Minimize cold-start impact**: Keep instrumentation lightweight in the function itself
- **Rich attributes over deep span trees**: One wide span beats ten narrow ones
- **Timing attributes**: Track sub-operation durations as attributes, not child spans
- **Correlation IDs**: Essential for connecting invocations across event-driven chains
