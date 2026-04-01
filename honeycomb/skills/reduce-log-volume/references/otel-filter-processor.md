# OTel Collector Filter Processor for Logs

Reference for generating OpenTelemetry Collector `filter` processor configurations to drop high-volume log templates.

## Processor Structure

The `filter` processor uses OTTL (OpenTelemetry Transformation Language) conditions to decide which log records to drop. Matching records are **excluded** from the pipeline.

```yaml
filter/log_templates:
  error_mode: ignore
  logs:
    # Simple unconditional rules (match any service)
    log_record:
      - IsMatch(body, "regex_pattern")

    # Per-service rules using named blocks with conditions
    log_record/service-name:
      conditions:
        - resource.attributes["service.name"] == "service-name"
      expressions:
        - IsMatch(body, "regex_pattern_1")
        - IsMatch(body, "regex_pattern_2")
```

## Key OTTL Functions

| Function | Use |
|----------|-----|
| `IsMatch(body, "regex")` | Regex match on the log body |
| `body == "exact string"` | Exact string match |
| `resource.attributes["service.name"] == "svc"` | Match by service name |

## Regex Tips for Log Templates

When converting log body patterns to regex:

- Escape special regex characters: `.` `(` `)` `[` `]` `{` `}` `+` `*` `?` `|` `^` `$`
- Replace UUIDs with: `[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}`
- Replace integers with: `[0-9]+`
- Replace IP addresses with: `[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+`
- Replace timestamps with broad patterns: `[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}`
- Use `.*` sparingly — prefer specific patterns to avoid over-matching

## Pipeline Placement

The filter processor should be placed in the logs pipeline **after** parsing/enrichment transforms but **before** export:

```yaml
service:
  pipelines:
    logs:
      receivers: [otlp]
      processors:
        - transform/parse_json_body    # parse first
        - transform/service_names      # enrich first
        - filter/log_templates         # then filter
        - batch
      exporters: [otlp/honeycomb]
```

## Merging with Existing Config

When a `filter/log_templates` block already exists:

1. **Do not create a duplicate processor** — merge into the existing one
2. For existing `log_record/service-name` blocks, append new expressions
3. For new services, add new `log_record/service-name` blocks
4. Preserve existing comments and formatting where possible
5. Add a comment above each new expression with the template and 24h volume

## Example Output

```yaml
filter/log_templates:
  error_mode: ignore
  logs:
    log_record/cart:
      conditions:
        - resource.attributes["service.name"] == "cart"
      expressions:
        # template: Added {Count} items to cart {CartId} | 24h volume: 1,234,567
        - IsMatch(body, "Added [0-9]+ items to cart [0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
        # template: Cache hit for product {ProductId} | 24h volume: 987,654
        - IsMatch(body, "Cache hit for product [0-9]+")

    log_record/api-gateway:
      conditions:
        - resource.attributes["service.name"] == "api-gateway"
      expressions:
        # template: GET {Path} {StatusCode} {Ms}ms | 24h volume: 2,345,678
        - IsMatch(body, "GET .+ [0-9]+ [0-9]+ms")
```
