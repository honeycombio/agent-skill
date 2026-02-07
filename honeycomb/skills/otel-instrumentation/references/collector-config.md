# OpenTelemetry Collector Configuration

The OTel Collector receives, processes, and exports telemetry data. Use it between
your application and Honeycomb for format conversion, processing, sampling, and routing.

## When to Use a Collector

- Converting from other formats (Zipkin, Jaeger, OpenTracing) to OTLP
- Adding common attributes across all services (e.g., deployment info)
- Tail sampling at the infrastructure level
- Routing to multiple backends
- Gateway/proxy designation for Service Map

## Basic Honeycomb Configuration

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: "0.0.0.0:4317"
      http:
        endpoint: "0.0.0.0:4318"

processors:
  batch:
    timeout: 1s
    send_batch_size: 1024

exporters:
  otlp/honeycomb:
    endpoint: "api.honeycomb.io:443"
    headers:
      x-honeycomb-team: "${HONEYCOMB_API_KEY}"

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp/honeycomb]
```

## Adding Attributes via Processor

Tag all spans with deployment info:

```yaml
processors:
  attributes:
    actions:
      - key: deployment.environment
        value: "production"
        action: upsert
      - key: net.component
        value: "proxy"
        action: upsert  # For gateway/proxy services in Service Map
```

## Tail Sampling Configuration

Sample based on trace characteristics (requires seeing complete traces):

```yaml
processors:
  tail_sampling:
    decision_wait: 10s
    num_traces: 100000
    policies:
      # Always keep error traces
      - name: errors
        type: status_code
        status_code:
          status_codes: [ERROR]
      # Always keep slow traces
      - name: slow-traces
        type: latency
        latency:
          threshold_ms: 5000
      # Sample 10% of everything else
      - name: probabilistic
        type: probabilistic
        probabilistic:
          sampling_percentage: 10
```

For production tail sampling, consider Honeycomb's **Refinery** which is purpose-built
for trace-aware sampling decisions and integrates natively with Honeycomb.

## Converting from Other Formats

### Zipkin to Honeycomb
```yaml
receivers:
  zipkin:
    endpoint: "0.0.0.0:9411"
```

### Jaeger to Honeycomb
```yaml
receivers:
  jaeger:
    protocols:
      grpc:
        endpoint: "0.0.0.0:14250"
      thrift_http:
        endpoint: "0.0.0.0:14268"
```

## Gateway for Service Map

To show a proxy/gateway in Honeycomb's Service Map, add `net.component: proxy`:

```yaml
processors:
  attributes:
    actions:
      - key: net.component
        value: "proxy"
        action: upsert
```
