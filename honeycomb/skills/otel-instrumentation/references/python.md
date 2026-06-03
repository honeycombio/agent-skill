# Python OpenTelemetry — In-Depth Guide

Additional detail for Python instrumentation beyond the basics in
`sdk-setup-by-language.md`. Covers framework-specific packages, async patterns,
programmatic SDK setup for ASGI apps, and attribute enrichment.

---

## Critical: async SQLAlchemy requires `.sync_engine`

**Read this before writing any SQLAlchemy instrumentation.** `SQLAlchemyInstrumentor`
does not support async engines directly. Passing the async engine raises
`NotImplementedError: asynchronous events are not implemented at this time`.

Always pass the underlying sync engine:

```python
# WRONG — raises NotImplementedError at startup
SQLAlchemyInstrumentor().instrument(engine=async_engine)

# CORRECT
SQLAlchemyInstrumentor().instrument(engine=async_engine.sync_engine)
```

This applies to `create_async_engine(...)` from `sqlalchemy.ext.asyncio`.

**After writing the call, verify the argument ends in `.sync_engine`.** If it reads
`engine=some_engine` without `.sync_engine`, the app will crash at startup with
`NotImplementedError: asynchronous events are not implemented at this time` — the
fix is always to append `.sync_engine` to the engine argument.

---

## Choosing Your Setup Approach

| Approach | When to use |
| :--- | :--- |
| `opentelemetry-instrument` CLI | Simple WSGI apps (Flask, Django); no code changes needed |
| Programmatic SDK init | ASGI apps (FastAPI, Starlette); gives full control over lifecycle |

For **FastAPI / NiceGUI / Starlette** always use programmatic setup. The CLI runner
doesn't integrate cleanly with ASGI lifespans and may miss startup instrumentation.

---

## Instrumentation Package Reference

Install only what the app actually uses. Each package auto-instruments its library
when `.instrument()` is called.

### Web frameworks
```bash
pip install opentelemetry-instrumentation-fastapi      # FastAPI + Starlette
pip install opentelemetry-instrumentation-flask        # Flask
pip install opentelemetry-instrumentation-django       # Django
pip install opentelemetry-instrumentation-aiohttp-server  # aiohttp server
```

### HTTP clients
```bash
pip install opentelemetry-instrumentation-httpx        # httpx (sync + async)
pip install opentelemetry-instrumentation-requests     # requests
pip install opentelemetry-instrumentation-aiohttp-client  # aiohttp client
pip install opentelemetry-instrumentation-urllib3      # urllib3
```

### Databases
```bash
pip install opentelemetry-instrumentation-sqlalchemy   # SQLAlchemy (sync + async)
pip install opentelemetry-instrumentation-asyncpg      # asyncpg (raw driver)
pip install opentelemetry-instrumentation-psycopg2     # psycopg2
pip install opentelemetry-instrumentation-sqlite3      # sqlite3 (stdlib)
pip install opentelemetry-instrumentation-redis        # redis-py
```

### Other
```bash
pip install opentelemetry-instrumentation-celery       # Celery tasks
pip install opentelemetry-instrumentation-logging      # stdlib logging bridge
pip install opentelemetry-instrumentation-system-metrics  # CPU, memory, GC
```

With `uv`:
```bash
uv add opentelemetry-sdk opentelemetry-exporter-otlp-proto-http \
       opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-sqlalchemy
```

---

## Programmatic Setup for ASGI Apps (FastAPI / Starlette)

Create a `telemetry.py` module. The SDK wiring is always the same; the
auto-instrumentation calls depend on what the app actually uses — inspect the
codebase and choose from the **Instrumentation Package Reference** above.

```python
import os
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
# Import only the instrumentors that match the libraries this app uses.
# Check pyproject.toml / requirements.txt, then see Package Reference above.


def configure_opentelemetry(**kwargs):
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return  # no-op when unconfigured

    resource = Resource.create()  # reads OTEL_SERVICE_NAME + OTEL_RESOURCE_ATTRIBUTES
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)

    # Call .instrument() for each library the app uses.
    # SQLAlchemy example — note .sync_engine (async engines crash without it):
    #   SQLAlchemyInstrumentor().instrument(engine=async_engine.sync_engine)
    # httpx example:
    #   HTTPXClientInstrumentor().instrument()
    # See Package Reference above for the full list.


def instrument_app(app):
    FastAPIInstrumentor.instrument_app(app)
```

Call order in `main.py`:
```python
# 1. Configure SDK and library auto-instrumentation (before app is created)
configure_opentelemetry(...)

app = FastAPI(lifespan=lifespan)

# 2. Mount all routers
init_api_routes(app)
init_gui_routes(app)

# 3. Instrument the fully-wired app
instrument_app(app)

# 4. NiceGUI only: if this app uses @ui.page() decorators, add the http.route
#    recovery middleware (see "NiceGUI / custom router" section below).
#    Skip this step for non-NiceGUI apps.
```

**Why order matters:** `FastAPIInstrumentor.instrument_app()` wraps the router list
at call time. If called before routes are mounted, some routes won't be captured.

---

## Adding Attributes to Existing Spans

Get the current span from context and annotate it — no new span needed:

```python
from opentelemetry import trace

span = trace.get_current_span()
span.set_attribute("user.id", str(user.id))
span.set_attribute("habit.id", habit_id)
span.set_attribute("habit.name", habit.name)
```

**In FastAPI request handlers**, the current span is the auto-instrumented HTTP span.
Adding attributes here enriches every request trace with business context.

---

## Middleware for Per-Request Attributes

For attributes that come from session/auth context (user ID, tenant), a middleware
runs inside the auto-instrumented HTTP span and can annotate it:

```python
from starlette.middleware.base import BaseHTTPMiddleware
from opentelemetry import trace

class OtelAttributeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        span = trace.get_current_span()
        # Read from session / auth token already attached by auth middleware
        if user_id := request.state.__dict__.get("user_id"):
            span.set_attribute("user.id", str(user_id))
        return await call_next(request)
```

Add it **after** `FastAPIInstrumentor.instrument_app()` and **after** auth middleware:
```python
app.add_middleware(OtelAttributeMiddleware)
```

### NiceGUI / custom router: recovering `http.route`

A common mistake: assuming that because `FastAPIInstrumentor` wraps the ASGI layer,
NiceGUI requests are fully instrumented. Spans *are* created — but `http.route` is
**not** populated. `FastAPIInstrumentor` reads `http.route` from FastAPI's route
registry, and NiceGUI's `@ui.page()` routes are never registered there. The result is
spans with no route, making every `http.route` breakdown in Honeycomb empty.

**Another common mistake: using `server_request_hook` to read `scope["route"]`.**
This looks correct but silently fails for NiceGUI — the route is not yet matched
in the scope when the hook fires (span creation). It is only populated *after*
routing completes. The only working fix is the middleware below, which runs after
`call_next` when routing has already happened.

If the app uses NiceGUI, add this after `instrument_app(app)` in `main.py`:

```python
from starlette.middleware.base import BaseHTTPMiddleware

class _RouteAttributeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        span = trace.get_current_span()
        if route := request.scope.get("route"):
            span.set_attribute("http.route", route.path)
        else:
            span.set_attribute("http.route", request.url.path)
        return response

app.add_middleware(_RouteAttributeMiddleware)
```

---

## Creating Custom Spans

Wrap business logic in a span to make it visible in the trace waterfall:

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

async def process_habit_completion(habit_id: str, done: bool):
    with tracer.start_as_current_span("habit.complete") as span:
        span.set_attribute("habit.id", habit_id)
        span.set_attribute("completion.done", done)
        # ... business logic ...
```

For async code, context propagates automatically through `async with` and
`start_as_current_span` — no manual context passing needed within a single
async task.
---

## Async Caveats

### asyncpg raw driver
If using `asyncpg` directly (no SQLAlchemy), use
`opentelemetry-instrumentation-asyncpg` and call
`AsyncPGInstrumentor().instrument()` before creating any connection pools.

### Background tasks / workers
Spans created in background `asyncio.Task`s are attached to the task's context,
not the request context. They arrive in Honeycomb as separate traces (expected).
Use `trace.use_span()` or `copy_context()` if you need to link them to the
originating request.

---

## Resource Attributes

Set custom resource attributes (shown on every span) via env var:

```bash
export OTEL_RESOURCE_ATTRIBUTES="deployment.environment=production,service.version=1.2.3"
```

Or programmatically:

```python
from opentelemetry.sdk.resources import Resource

resource = Resource.create({
    "service.name": "my-app",
    "deployment.environment": "production",
    "service.version": "1.2.3",
})
provider = TracerProvider(resource=resource)
```

`Resource.create()` with no arguments reads `OTEL_SERVICE_NAME` and
`OTEL_RESOURCE_ATTRIBUTES` from the environment automatically.

---

## Exception Slugs

Tag each error site with a static identifier so errors are greppable in code and
queryable by slug in Honeycomb:

```python
from opentelemetry import trace

span = trace.get_current_span()
try:
    result = await do_something()
except ValueError as e:
    span.set_attribute("exception.slug", "err-invalid-habit-data")
    span.set_attribute("error", True)
    span.record_exception(e)
    raise
```

Query: `WHERE error = true AND exception.slug does-not-exist` — finds untagged error
paths that still need slugs.
