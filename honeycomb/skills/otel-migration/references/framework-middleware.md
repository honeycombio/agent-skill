# Framework-Specific OTel Middleware

OTel middleware for HTTP frameworks provides automatic spans for every inbound request with
zero code changes to handlers. The critical detail is how each framework exposes the
OTel-enriched context — getting this wrong silently breaks traces.

## Go Frameworks

### net/http (standard library)

```go
import "go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"

handler := otelhttp.NewHandler(mux, "server")
http.ListenAndServe(":8080", handler)
```

**Context access:** `r.Context()` — standard, no gotchas.

### Fiber v2

```go
import "go.opentelemetry.io/contrib/instrumentation/github.com/gofiber/fiber/otelfiber"

app := fiber.New()
app.Use(otelfiber.Middleware())
```

**Context access:** `c.UserContext()` — NOT `c.Context()`.

**Critical gotcha:** `c.Context()` returns the underlying fasthttp context, which does NOT
contain the OTel span. It compiles, runs, and returns results — but traces silently break.
You get orphaned spans instead of connected parent-child relationships. There is no error or
warning. You only notice when you look at your tracing backend and see disconnected traces.

```go
// WRONG — returns fasthttp context, no OTel span
ctx := c.Context()

// RIGHT — returns context with OTel span
ctx := c.UserContext()
```

### Gin

```go
import "go.opentelemetry.io/contrib/instrumentation/github.com/gin-gonic/gin/otelgin"

r := gin.Default()
r.Use(otelgin.Middleware("service-name"))
```

**Context access:** `c.Request.Context()` — get it from the underlying `*http.Request`.

### Echo

```go
import "go.opentelemetry.io/contrib/instrumentation/github.com/labstack/echo/otelecho"

e := echo.New()
e.Use(otelecho.Middleware("service-name"))
```

**Context access:** `c.Request().Context()` — get it from the underlying `*http.Request`.

### Chi

Chi uses standard `net/http` handlers, so use `otelhttp`:

```go
import "go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"

r := chi.NewRouter()
r.Use(func(next http.Handler) http.Handler {
    return otelhttp.NewHandler(next, "server")
})
```

**Context access:** `r.Context()` — standard, no gotchas.

## Python Frameworks

Python OTel instrumentation libraries use monkey-patching or middleware that stores the span
in a `ContextVar`. Context is automatically available — no special accessor needed.

### Flask

```bash
pip install opentelemetry-instrumentation-flask
```

```python
from opentelemetry.instrumentation.flask import FlaskInstrumentor

FlaskInstrumentor().instrument_app(app)
```

Context is automatic. Use `trace.get_current_span()` anywhere in a request handler.

### Django

```bash
pip install opentelemetry-instrumentation-django
```

Add `"opentelemetry.instrumentation.django"` to Django middleware, or call:

```python
from opentelemetry.instrumentation.django import DjangoInstrumentor

DjangoInstrumentor().instrument()
```

Context is automatic. Works with Django views, class-based views, and DRF.

### FastAPI / Starlette

```bash
pip install opentelemetry-instrumentation-fastapi
```

```python
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

FastAPIInstrumentor.instrument_app(app)
```

Context propagates through async handlers automatically.

## Node.js Frameworks

Node.js OTel uses `AsyncLocalStorage` to propagate context. Instrumentation libraries
monkey-patch framework internals to inject spans.

### Express

```bash
npm install @opentelemetry/instrumentation-express @opentelemetry/instrumentation-http
```

Both packages are needed — `instrumentation-http` for the HTTP server spans,
`instrumentation-express` for route-level spans.

Context is automatic. Use `trace.getActiveSpan()` in any middleware or route handler.

### Fastify

```bash
npm install @opentelemetry/instrumentation-fastify @opentelemetry/instrumentation-http
```

Context is automatic through the plugin system.

### Koa

```bash
npm install @opentelemetry/instrumentation-koa @opentelemetry/instrumentation-http
```

Context is automatic. Works with Koa middleware and route handlers.

### Hapi

```bash
npm install @opentelemetry/instrumentation-hapi @opentelemetry/instrumentation-http
```

Context is automatic.

## Java Frameworks

The Java agent auto-instruments most frameworks with zero code changes. If using the agent,
no manual middleware setup is needed.

### Spring Boot (with Java agent)

No code changes — the agent instruments Spring MVC/WebFlux automatically.

### Spring Boot (without Java agent)

Use the Spring Boot starter:

```xml
<dependency>
    <groupId>io.opentelemetry.instrumentation</groupId>
    <artifactId>opentelemetry-spring-boot-starter</artifactId>
</dependency>
```

### Jakarta Servlet

The Java agent instruments servlets automatically. Without the agent, use the library
instrumentation:

```xml
<dependency>
    <groupId>io.opentelemetry.instrumentation</groupId>
    <artifactId>opentelemetry-servlet-5.0</artifactId>
</dependency>
```

**Pain point:** Thread pool context loss. If a servlet dispatches work to a thread pool
(common in async servlets), wrap tasks with `Context.current().wrap(...)`.

## .NET Frameworks

### ASP.NET Core

```csharp
builder.Services.AddOpenTelemetry()
    .WithTracing(tracing => tracing
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddOtlpExporter());
```

Context propagates automatically through the ASP.NET Core middleware pipeline and
async/await chains. `Activity.Current` is available in controllers, middleware, and services.

### ASP.NET (Framework / legacy)

```bash
dotnet add package OpenTelemetry.Instrumentation.AspNet
```

Uses `TelemetryHttpModule` registered in `web.config`.

## Ruby Frameworks

### Rails

```ruby
# Gemfile
gem "opentelemetry-instrumentation-rails"
gem "opentelemetry-instrumentation-all"  # or pick specific gems
```

```ruby
OpenTelemetry::SDK.configure do |c|
  c.use "OpenTelemetry::Instrumentation::Rails"
end
```

Context is automatic through Rails middleware and ActiveSupport instrumentation.

### Sinatra

```ruby
gem "opentelemetry-instrumentation-sinatra"
```

```ruby
OpenTelemetry::SDK.configure do |c|
  c.use "OpenTelemetry::Instrumentation::Sinatra"
end
```
