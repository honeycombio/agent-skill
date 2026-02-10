---
name: beeline-migration
description: >
  This skill should be used when the user asks to "migrate from Beelines",
  "upgrade from Beeline to OpenTelemetry", "migrate to OTel", "replace Beelines",
  "Beeline end of life", "Beeline EOL", "switch from Beeline to OTel",
  "migrate Go Beeline", "migrate Python Beeline", "migrate Node Beeline",
  "migrate Java Beeline", "migrate Ruby Beeline", "W3C trace headers",
  "W3C propagation", "incremental migration to OpenTelemetry",
  or needs guidance on migrating from Honeycomb Beelines to OpenTelemetry SDKs.
  For OTel SDK setup after migration, see the otel-instrumentation skill.
metadata:
  version: "1.0.0"
---

# Beeline to OpenTelemetry Migration

Step-by-step guide for migrating from Honeycomb Beelines (now End of Life)
to OpenTelemetry instrumentation.

## Status

Honeycomb Beelines have reached **End of Life** and are **archived**. All new
instrumentation should use OpenTelemetry. Existing Beeline users should migrate
as soon as practical.

## Migration Strategy

Migration follows a two-phase approach that allows incremental, service-by-service
migration without breaking distributed traces.

### Phase 1: Enable W3C Trace Propagation (All Services)

Before migrating any service to OTel, **all** services must support W3C trace
headers. This enables Beeline and OTel services to share trace context.

1. Upgrade each Beeline to the minimum version supporting W3C headers
2. Configure each Beeline to use W3C propagation format
3. Deploy all services with W3C enabled
4. **Verify**: Traces still link correctly across services

**Minimum Beeline versions for W3C support:**

| Language | Minimum Version |
|----------|----------------|
| Go | 1.4.0 |
| Java | 1.7.0 |
| Node.js | 3.2.2 |
| Python | 2.18.0 |
| Ruby | 2.8.0 |

### Phase 2: Migrate Each Service to OTel (One at a Time)

After all services support W3C headers:

1. Choose a service to migrate (start with leaf services — fewest dependencies)
2. Replace Beeline SDK with OpenTelemetry SDK
3. Configure OTLP exporter to point to Honeycomb
4. Add auto-instrumentation libraries
5. Replicate any custom Beeline instrumentation in OTel
6. Deploy and verify traces still connect
7. Repeat for next service

**Key rule**: Complete Phase 1 across ALL services before starting Phase 2 on ANY service.

## W3C Propagation Configuration

### Go Beeline
```go
beeline.Init(beeline.Config{
    HTTPPropagationHook: propagation.W3C,
})
```

### Python Beeline
```python
beeline.init(
    http_trace_propagation_hook=beeline.propagation.w3c.http_trace_propagation_hook,
    http_trace_parser_hook=beeline.propagation.w3c.http_trace_parser_hook,
)
```

### Node.js Beeline
```javascript
const beeline = require("honeycomb-beeline")({
    httpTraceParserHook: beeline.w3c.httpTraceParserHook,
    httpTracePropagationHook: beeline.w3c.httpTracePropagationHook,
});
```

For Java and Ruby configurations, consult `${CLAUDE_PLUGIN_ROOT}/skills/beeline-migration/references/w3c-propagation.md`.

## Service Migration Checklist

For each service being migrated from Beeline to OTel:

- [ ] Beeline version supports W3C (Phase 1 complete)
- [ ] Install OTel SDK and OTLP exporter packages
- [ ] Configure OTLP endpoint and headers for Honeycomb
- [ ] Set `OTEL_SERVICE_NAME` to match existing service name
- [ ] Add auto-instrumentation libraries (HTTP, DB, etc.)
- [ ] Port custom spans: Beeline `startSpan()` -> OTel `tracer.start_span()`
- [ ] Port custom attributes: Beeline `addField()` -> OTel `span.set_attribute()`
- [ ] Remove Beeline dependency
- [ ] Deploy and verify: traces link across Beeline and OTel services
- [ ] Verify: custom attributes appear in Honeycomb

## Common Pitfalls

- **Skipping Phase 1**: Migrating to OTel before W3C is everywhere breaks trace linking
- **Changing service names**: Keep `OTEL_SERVICE_NAME` identical to Beeline service name
- **Missing custom instrumentation**: Audit Beeline `addField()` calls before removing
- **Different attribute names**: OTel auto-instrumentation may use different field names than Beeline

## Additional Resources

### Reference Files
- **`${CLAUDE_PLUGIN_ROOT}/skills/beeline-migration/references/migration-steps-by-language.md`** — Detailed migration code for each language
- **`${CLAUDE_PLUGIN_ROOT}/skills/beeline-migration/references/w3c-propagation.md`** — Complete W3C configuration for all Beeline languages
