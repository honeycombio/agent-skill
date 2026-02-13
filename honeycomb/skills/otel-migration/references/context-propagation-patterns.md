# Context Propagation Patterns by Language

Language-specific patterns for retrofitting trace context propagation into existing codebases.
Context propagation is the mechanism that links spans into connected traces. Without it, you
get orphaned spans instead of a trace tree.

The difficulty of context propagation varies by language. Go requires explicit threading of
`context.Context` through every function call — the hardest case. Most other languages use
thread-local or async-local storage that propagates automatically within a thread or async chain.

## Go

Go requires explicit `context.Context` parameter threading. The OTel span lives inside the
context, so every function in the call chain between your HTTP handler and your I/O operations
must accept and pass `context.Context`.

### The core problem

Functions that look like this:

```go
func GetUser(id string) (*User, error) {
    return db.Query("SELECT * FROM users WHERE id = ?", id)
}
```

Need to become:

```go
func GetUser(ctx context.Context, id string) (*User, error) {
    return db.QueryContext(ctx, "SELECT * FROM users WHERE id = ?", id)
}
```

This change cascades through every caller of `GetUser`, and every caller of those callers,
up to the HTTP handler where the context originates.

### Pattern 1: Wrapper functions for backward compatibility

When you can't change all callers at once, add a context-accepting variant:

```go
// Original — keep during migration
func (ep *Endpoint) EvaluateHealth() *Result {
    return ep.EvaluateHealthWithCtx(context.Background())
}

// New — accepts context for trace propagation
func (ep *Endpoint) EvaluateHealthWithCtx(ctx context.Context) *Result {
    ctx, span := tracer.Start(ctx, "evaluate health")
    defer span.End()
    // actual implementation using ctx
}
```

This lets you migrate callers incrementally. Once all callers pass real context,
remove the wrapper and rename.

### Pattern 2: Interface-driven migration

Change the interface first, then fix every compilation error:

```go
// Before
type Store interface {
    GetUser(id string) (*User, error)
    InsertUser(user *User) error
}

// After — the compiler catches every call site
type Store interface {
    GetUser(ctx context.Context, id string) (*User, error)
    InsertUser(ctx context.Context, user *User) error
}
```

The compiler becomes your migration checklist. This is the most reliable approach.

### Pattern 3: Goroutine context propagation

Background goroutines need new spans per iteration, not the parent context's span:

```go
func monitorEndpoint(ctx context.Context) {
    ticker := time.NewTicker(interval)
    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            // Create a NEW span for each tick
            tickCtx, span := tracer.Start(ctx, "monitor tick")
            executeCheck(tickCtx)
            span.End()
        }
    }
}
```

If you pass the goroutine's raw `ctx` without starting a new span, all iterations appear
under a single never-ending span.

### Pattern 4: Coexisting with custom context mechanisms

Some codebases have their own key-value passing mechanisms. Keep both — they serve
different purposes:

```go
func (ep *Endpoint) EvaluateHealth(ctx context.Context, appCtx *AppContext) *Result {
    // ctx for OTel trace propagation
    // appCtx for application-level value sharing
}
```

Don't try to merge custom mechanisms into `context.Context`.

### Where to use context.Background()

- Program startup / initialization code (no parent trace exists)
- Background goroutine entry points that start their own traces
- Test code (unless testing trace propagation itself)

Everywhere else, propagate a real context from the request or entry point.

## Python

Python uses `contextvars` (Python 3.7+) for implicit context propagation. The OTel SDK stores
the current span in a `ContextVar`, so spans created with `start_as_current_span` automatically
become the parent of subsequent child spans within the same thread or async context.

### Automatic propagation with context managers

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

def handle_request():
    with tracer.start_as_current_span("handle request"):
        # Child spans automatically become children of "handle request"
        process_data()

def process_data():
    with tracer.start_as_current_span("process data"):
        # This span is automatically a child — no explicit context passing needed
        result = db_query()
    return result
```

Unlike Go, you do **not** need to add context parameters to every function. The `contextvars`
module handles propagation automatically within a thread.

### Decorator pattern

```python
@tracer.start_as_current_span("process_order")
def process_order(order_id: str):
    # Span automatically created and ended when function returns
    validate_order(order_id)
    charge_payment(order_id)
```

### Pain point: Thread pools

`contextvars` context does NOT automatically propagate to threads in a `ThreadPoolExecutor`.
You must copy context explicitly:

```python
import contextvars
from concurrent.futures import ThreadPoolExecutor

def handle_request():
    with tracer.start_as_current_span("handle request"):
        ctx = contextvars.copy_context()
        with ThreadPoolExecutor() as executor:
            # ctx.run ensures the span context propagates to the worker thread
            future = executor.submit(ctx.run, process_in_background)
            result = future.result()
```

### Pain point: Multiprocessing

Context does not propagate across process boundaries. For `multiprocessing`, you must
serialize and re-inject trace context manually (inject/extract with W3C headers).

### Pain point: Celery and task queues

Celery tasks run in separate worker processes. Use the `opentelemetry-instrumentation-celery`
library, which handles context serialization into task headers automatically.

### Accessing the current span anywhere

```python
from opentelemetry import trace

def enrich_span():
    span = trace.get_current_span()
    span.set_attribute("user.id", current_user_id)
```

## Java

Java uses thread-local `io.opentelemetry.context.Context` for propagation. If you use the
Java agent (recommended), context propagation is handled automatically for most frameworks.
The pain points are thread pools, CompletableFuture, and reactive streams.

### Automatic propagation (Java agent)

With the Java agent, instrumented frameworks (Spring, Servlet, JDBC, etc.) automatically
propagate context. Manual spans participate in the existing context:

```java
import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.context.Scope;

Tracer tracer = GlobalOpenTelemetry.getTracer("my-service");

public void handleRequest() {
    Span span = tracer.spanBuilder("process order").startSpan();
    try (Scope scope = span.makeCurrent()) {
        // Child spans in called methods automatically become children
        processOrder();
    } finally {
        span.end();
    }
}
```

### Pain point: Thread pools and ExecutorService

Thread-local context does NOT propagate to threads in a thread pool. Wrap your executor:

```java
import io.opentelemetry.context.Context;

ExecutorService executor = Executors.newFixedThreadPool(4);

public void handleRequest() {
    Span span = tracer.spanBuilder("handle request").startSpan();
    try (Scope scope = span.makeCurrent()) {
        // Capture current context
        Context current = Context.current();
        // Wrap the task to propagate context
        executor.submit(current.wrap(() -> {
            // Context is now available in this thread
            processInBackground();
        }));
    } finally {
        span.end();
    }
}
```

Use `Context.current().wrap(Runnable)` or `Context.current().wrap(Callable)` to propagate
context into thread pool tasks.

### Pain point: CompletableFuture

CompletableFuture chains lose context when switching threads:

```java
// WRONG — context lost in thenApplyAsync
CompletableFuture.supplyAsync(() -> fetchData())
    .thenApplyAsync(data -> processData(data));

// RIGHT — capture and propagate context
Context ctx = Context.current();
CompletableFuture.supplyAsync(ctx.wrap(() -> fetchData()))
    .thenApplyAsync(ctx.wrap(data -> processData(data)));
```

### Pain point: Reactive streams (Project Reactor, RxJava)

Reactive frameworks require special OTel integrations. For Project Reactor, use the
`opentelemetry-reactor-netty` instrumentation. For Spring WebFlux, use
`opentelemetry-spring-webflux`. These hook into the reactive scheduling to propagate context.

### Accessing the current span

```java
Span currentSpan = Span.current();
currentSpan.setAttribute("user.id", userId);
```

## Node.js

Node.js uses `AsyncLocalStorage` (Node 16+) for automatic context propagation across
async/await boundaries. The OTel SDK's `AsyncHooksContextManager` (or
`AsyncLocalStorageContextManager`) handles this.

### Automatic propagation with startActiveSpan

```javascript
const { trace } = require('@opentelemetry/api');
const tracer = trace.getTracer('my-service');

function handleRequest(req, res) {
  tracer.startActiveSpan('handle request', (span) => {
    // Child spans automatically become children
    processData();
    span.end();
  });
}

function processData() {
  tracer.startActiveSpan('process data', (span) => {
    // Automatically a child of "handle request" — no explicit context passing
    span.end();
  });
}
```

### Pain point: Callback-based APIs

Older Node.js code using callbacks (before async/await) may break the async context chain.
Use `context.with()` to explicitly bind context:

```javascript
const { context, trace } = require('@opentelemetry/api');

function handleRequest(req, res) {
  tracer.startActiveSpan('handle request', (span) => {
    const ctx = context.active();
    // Bind context to the callback
    legacyLib.doSomething(context.bind(ctx, (err, result) => {
      tracer.startActiveSpan('process result', (childSpan) => {
        // Context is preserved
        childSpan.end();
      });
      span.end();
    }));
  });
}
```

### Pain point: Native addons

Native C++ addons that perform async work outside the Node.js event loop may not participate
in `AsyncLocalStorage`. Context will be lost across these boundaries. There is no general
fix — you must manually capture and restore context around native addon calls.

### Accessing the current span

```javascript
const { trace } = require('@opentelemetry/api');

function enrichSpan() {
  const span = trace.getActiveSpan();
  span?.setAttribute('user.id', currentUserId);
}
```

## .NET

.NET uses `System.Diagnostics.Activity` and `ActivitySource` which map to OTel spans and
tracers respectively. Context propagates automatically through `async/await` via `AsyncLocal<T>`.
This makes .NET one of the easiest languages for context propagation.

### Automatic propagation

```csharp
using System.Diagnostics;

var activitySource = new ActivitySource("MyService");

public async Task HandleRequest()
{
    using var activity = activitySource.StartActivity("handle request");
    // Child activities automatically become children
    await ProcessData();
}

public async Task ProcessData()
{
    using var activity = activitySource.StartActivity("process data");
    // Automatically a child — no explicit context passing needed
    await Task.Delay(100);
}
```

The `using` statement ensures the activity (span) is ended when the scope exits.
`async/await` propagates context automatically through `AsyncLocal<T>`.

### Pain point: Manual thread creation

`Activity.Current` does NOT propagate across manually created threads (new `Thread()`).
Use `Task.Run()` or `ThreadPool.QueueUserWorkItem()` instead, which participate in
`ExecutionContext` flow:

```csharp
// WRONG — context lost
var thread = new Thread(() => {
    // Activity.Current is null here
    DoWork();
});
thread.Start();

// RIGHT — context propagates
await Task.Run(() => {
    // Activity.Current is available
    DoWork();
});
```

### Pain point: ExecutionContext suppression

If code calls `ExecutionContext.SuppressFlow()`, context propagation is disabled for
subsequent async operations. This is rare but can cause subtle trace breaks.

### Accessing the current activity

```csharp
var current = Activity.Current;
current?.SetTag("user.id", userId);
```

## Ruby

Ruby uses thread-local context storage. The OTel SDK stores the current span in a
thread-local variable, so spans created within the same thread are automatically linked.

### Automatic propagation with instrumentation

With `opentelemetry-instrumentation-all`, most Rails/Sinatra middleware, ActiveRecord,
and HTTP clients are automatically instrumented:

```ruby
require "opentelemetry/sdk"
require "opentelemetry/instrumentation/all"

OpenTelemetry::SDK.configure do |c|
  c.service_name = "my-service"
  c.use_all
end
```

### Creating child spans

```ruby
tracer = OpenTelemetry.tracer_provider.tracer("my-service")

def handle_request
  tracer.in_span("handle request") do |span|
    # Child spans automatically become children
    process_data
  end
end

def process_data
  tracer.in_span("process data") do |span|
    # Automatically a child — no explicit context passing
  end
end
```

### Pain point: Thread pools and concurrent-ruby

Thread-local context does NOT propagate to new threads:

```ruby
# WRONG — context lost in new thread
Thread.new { process_in_background }

# RIGHT — capture and propagate context
context = OpenTelemetry::Context.current
Thread.new do
  OpenTelemetry::Context.with_current(context) do
    process_in_background
  end
end
```

### Pain point: Sidekiq and background jobs

Sidekiq jobs run in separate threads (or processes). Use
`opentelemetry-instrumentation-sidekiq` to automatically propagate trace context
through job enqueue/dequeue.

### Accessing the current span

```ruby
current_span = OpenTelemetry::Trace.current_span
current_span.set_attribute("user.id", current_user_id)
```
