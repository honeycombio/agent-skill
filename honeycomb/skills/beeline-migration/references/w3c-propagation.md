# W3C Trace Propagation Configuration

Complete W3C header configuration for all Beeline languages. This must be done
for ALL services before migrating any service to OpenTelemetry.

## Why W3C First?

Beelines default to Honeycomb's proprietary trace header format. OpenTelemetry uses
W3C TraceContext headers. Without W3C on Beelines, migrating one service to OTel would
break trace linking with remaining Beeline services.

W3C TraceContext uses the `traceparent` HTTP header to propagate trace context.

## Go Beeline (>= 1.4.0)

```go
import "github.com/honeycombio/beeline-go/propagation"

beeline.Init(beeline.Config{
    WriteKey:               "YOUR_API_KEY",
    Dataset:                "my-service",
    HTTPPropagationHook:    propagation.W3C,
    HTTPTracePropagationHook: propagation.W3C,
})
```

## Java Beeline (>= 1.7.0)

```java
// Configure via system property or environment variable:
// -Dhoneycomb.beeline.trace.propagation=w3c
// or
// HONEYCOMB_TRACE_PROPAGATION=w3c

BeelineConfig config = BeelineConfig.builder()
    .writeKey("YOUR_API_KEY")
    .dataset("my-service")
    .tracePropagation("w3c")
    .build();
```

## Node.js Beeline (>= 3.2.2)

```javascript
const beeline = require("honeycomb-beeline")({
    writeKey: "YOUR_API_KEY",
    dataset: "my-service",
    serviceName: "my-service",
    httpTraceParserHook: beeline.w3c.httpTraceParserHook,
    httpTracePropagationHook: beeline.w3c.httpTracePropagationHook,
});
```

## Python Beeline (>= 2.18.0)

```python
import beeline
from beeline.propagation import w3c

beeline.init(
    writekey="YOUR_API_KEY",
    dataset="my-service",
    service_name="my-service",
    http_trace_propagation_hook=w3c.http_trace_propagation_hook,
    http_trace_parser_hook=w3c.http_trace_parser_hook,
)
```

## Ruby Beeline (>= 2.8.0)

```ruby
Honeycomb.configure do |config|
  config.write_key = "YOUR_API_KEY"
  config.dataset = "my-service"
  config.service_name = "my-service"
  config.http_trace_parser_hook = Honeycomb::Propagation::W3C.method(:parse_rack_env)
  config.http_trace_propagation_hook = Honeycomb::Propagation::W3C.method(:propagation_hook)
end
```

## Verification

After enabling W3C on all services:

1. Make a request that crosses at least 2 services
2. In Honeycomb, find the trace and verify all services appear
3. Check that the `traceparent` header is being passed (visible in network tools)
4. Confirm span parent-child relationships are correct in the waterfall view
