---
name: reduce-log-volume
description: >
  Analyze log body patterns in Honeycomb to find high-volume message templates,
  then optionally update the OTel Collector config to filter them. Use when
  investigating noisy logs or optimizing log volume. Trigger phrases: "reduce
  log volume", "noisy logs", "filter logs", "log templates", "high-volume logs",
  "log body patterns", "optimize log volume", "cut log noise".
metadata:
  version: "1.0.0"
allowed-tools:
  - mcp__honeycomb__run_query
  - mcp__honeycomb__get_query_results
  - mcp__honeycomb__get_workspace_context
  - mcp__honeycomb__get_environment
  - mcp__honeycomb__get_dataset
  - mcp__honeycomb__get_dataset_columns
  - mcp__honeycomb__find_columns
  - Read
  - Edit
  - Write
  - Glob
  - Grep
  - Bash(echo *)
  - AskUserQuestion
---

# Log Template Analysis

Analyze log body patterns in a Honeycomb environment and dataset to identify high-volume message templates, then optionally generate OTel Collector filter config to drop them.

Ask the user which environment (and optionally which dataset) to analyze if not already clear from context.

## Step 0: Read existing collector config

Before doing any analysis, find and read the current OTel Collector config in the project. Look for:
- `**/collector/*.yaml`
- `**/otel-collector*.yaml`
- `**/values*.yaml` containing `processors:`

Parse any existing `filter/log_templates` processor block to build a list of **already-filtered patterns**. These will be excluded from the results in Step 2 so you don't re-suggest rules that are already in place.

## Step 1: Discover log body patterns

Use the Honeycomb MCP tools to find the top message templates by volume.

### If dataset is 'all' or not provided:
1. Call `get_workspace_context` to orient yourself
2. Call `get_environment` with the environment slug to list datasets
3. Query across the environment using `run_query` with `environment_wide_query: true`:
   - Filter: `meta.signal_type = log`
   - Breakdown by `service.name`
   - Time range: 24h
   - Order by COUNT descending, limit 15
4. For **each of the top 10 services by volume**, query that service's dataset individually

### If a specific dataset is provided:
1. Query that dataset directly

### For each dataset, find message templates:

First, get an initial view of body patterns by querying with `breakdowns: ["body"]`, `limit: 20`, ordered by COUNT descending. Only use `include_samples: false` to reduce response size.

Then build calculated fields that normalize the log `body` into template strings by replacing variable parts with placeholders. Use a chain of IF/REG_MATCH or IF/CONTAINS expressions to classify each body into a named template.

Common variable patterns to replace with placeholders:
- UUIDs: `{UserId}`, `{TraceId}`, `{RequestId}`
- Numbers: `{Count}`, `{Ms}`, `{Offset}`, `{Quantity}`
- Product/entity IDs: `{ProductId}`, `{OrderId}`
- IP addresses: `{IP}`
- Timestamps in log lines: `{Timestamp}`
- Email addresses: `{Email}`
- File paths: `{Path}`

**Use `breakdowns: ["msg_template"]` and `orders: [{"op": "COUNT", "order": "descending"}]` with `limit: 15`** to get the top templates per dataset.

**Validate counts**: After identifying templates, run a second pass using `SUM` of calculated fields with `REG_MATCH` to get exact verified counts per template.

## Step 2: Present results

Exclude any templates that match patterns already present in the collector's `filter/log_templates` block (from Step 0).

Present a single table with the remaining templates across all services, sorted by count descending, showing only the **top 10**:

```
| # | Service | Template | Examples | 24h Count |
```

- The Template column should use `{Placeholder}` syntax for variable parts (like messagetemplates.org)
- The Examples column should contain two different real example log body values separated by `<br>` so they render on separate lines within the same cell
- Include the validated 24h count
- Below the table, show the total log volume and what percentage the top 10 represents
- If patterns were excluded because they already exist in the config, note how many were skipped

Wait for the user to review and confirm which patterns they want to filter.

## Step 3: Generate collector filter config

Once the user selects which templates to filter, generate an OpenTelemetry Collector `filter` processor config.

### Generate the filter processor:

For each selected template, create a filter rule using the OTel Collector's `filter` processor with OTTL conditions on `body`. Use `IsMatch(body, "regex")` for patterns with variables, or string equality for static templates.

**Group rules by service using `conditions` to avoid repeating the service name on every rule.** Use named `log_record` blocks with `conditions` for the service name check, and list the body match expressions under `expressions`:

```yaml
filter/log_templates:
  error_mode: ignore
  logs:
    # Templates spanning all services (no service condition needed)
    log_record:
      - IsMatch(body, "{regex_for_cross_service_pattern}")

    # Per-service template groups using conditions
    log_record/cart:
      conditions:
        - resource.attributes["service.name"] == "cart"
      expressions:
        # template: {template} | 24h volume: {count}
        - IsMatch(body, "{regex}")
        - IsMatch(body, "{regex}")

    log_record/api-gateway:
      conditions:
        - resource.attributes["service.name"] == "api-gateway"
      expressions:
        - IsMatch(body, "{regex}")
```

If there is already a `filter/log_templates` block in the config, **merge** the new rules into it rather than creating a duplicate. Add new `log_record/{service}` blocks or append expressions to existing ones.

### Show the user:
1. The complete `filter/log_templates` processor block (merged with any existing rules)
2. The updated `service.pipelines.logs.processors` list showing where to insert it — place it after any processors that generate or parse the log body (e.g. `transform/parse_json_body`) but before other transforms. Skip this if it's already in the pipeline.
3. The estimated daily event reduction

**Do NOT apply changes yet.** Show the diff and ask for confirmation.

## Step 4: Apply changes

Only after the user confirms, edit the collector config file to:
1. Add or update the `filter/log_templates` processor under `config.processors`
2. Add `filter/log_templates` to the logs pipeline processor list (if not already present)

Show the final diff for review.
