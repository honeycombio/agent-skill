---
name: Honeycomb Query Patterns
description: >
  This skill should be used when the user asks to "query Honeycomb", "search traces",
  "find slow requests", "count errors", "build a Honeycomb query", "use GROUP BY",
  "filter events", "use VISUALIZE", "check latency", "find outliers by field",
  "use relational fields", "query across services", "use root. or parent. or child. prefixes",
  "write a Honeycomb query", "analyze performance", "find error patterns",
  "discover columns", "find fields", "what fields exist", "what data is available",
  "query across datasets", "environment-wide query", "check what columns are available",
  "create a board", "find existing boards", "look at past queries",
  or needs help constructing queries against Honeycomb data.
version: 1.0.0
---

# Honeycomb Query Patterns

Comprehensive reference for constructing effective Honeycomb queries via the MCP server.
Covers context discovery, all query clauses, relational fields, calculated fields,
boards, and common patterns.

## Before You Query: Essential Checklist

1. Call `get_workspace_context` to see available environments and datasets
2. Call `find_columns` or `get_dataset_columns` to discover available fields
3. Confirm the environment slug and dataset slug
4. Start with a broad query, then narrow with WHERE filters
5. Use HEATMAP for distributions, percentiles for latency — never AVG for latency

## MCP Tools for Querying

**Context Discovery (use before querying):**
- **`get_workspace_context`** — Starting point: team info, environments, default datasets, common columns
- **`get_environment`** — Environment details with dataset list (paginated)
- **`get_dataset`** — Dataset schema: columns and calculated fields (paginated)
- **`get_dataset_columns`** — Column list with sample values for a specific dataset
- **`find_columns`** — Semantic search for columns matching a query or keywords

**Query Execution:**
- **`run_query`** — Execute a query with calculations, filters, breakdowns, time range
- **`get_query_results`** — Retrieve results from an existing query run (by URL, run PK, or query ID)
- **`find_queries`** — Search query history and saved queries for relevant prior work

**Post-Query Analysis:**
- **`run_bubbleup`** — Compare outlier selection against baseline to identify differentiators

**Boards:**
- **`create_board`** — Create a new Board with query results, SLOs, and text panels
- **`list_boards`** — List boards in an environment or retrieve a specific board by ID

## Query Structure

Honeycomb queries use up to six clauses, mapped to `run_query` parameters:

| Clause | `run_query` Parameter | Purpose |
|--------|-----------------------|---------|
| **VISUALIZE** | `calculations` | Aggregation operations (COUNT, P99, HEATMAP, etc.) |
| **WHERE** | `filters` | Filter events by field conditions |
| **GROUP BY** | `breakdowns` | Group results by field values |
| **ORDER BY** | `orders` | Sort result rows |
| **LIMIT** | `limit` | Cap number of result groups |
| **Calculated Fields** | `calculated_fields` | Inline derived columns |

### Time Range Options

The `run_query` tool accepts human-readable time formats:
- **Relative duration**: `time_range: "24h"`, `"7d"`, `"2h30m"`
- **Relative expressions**: `start_time: "-24h"`, `end_time: "now"`
- **Absolute datetime**: `start_time: "2024-01-15T10:00:00Z"`, `end_time: "2024-01-15T12:00:00Z"`
- **Simple dates**: `start_time: "2024-01-15"`, `end_time: "2024-01-16"`
- **Default**: 2 hours if no time parameters specified

Prefer human-readable formats. Avoid calculating epoch timestamps.

### Environment-Wide Queries

Set `environment_wide_query: true` to query across all datasets in an environment.
Useful for cross-service analysis. Not available in legacy environments.

## Translating to run_query

The examples in this skill use Honeycomb Query Builder notation (VISUALIZE, WHERE, GROUP BY) for readability. When calling `run_query`, translate them to `query_spec` JSON.

**Example — Slowest endpoints:**

Shorthand: `P99(duration_ms) WHERE is_root GROUP BY http.route ORDER BY P99(duration_ms) DESC LIMIT 20`

Equivalent `query_spec`:
```json
{
  "calculations": [{ "op": "P99", "column": "duration_ms" }],
  "filters": [{ "column": "is_root", "op": "=", "value": true }],
  "breakdowns": ["http.route"],
  "orders": [{ "op": "P99", "column": "duration_ms", "order": "descending" }],
  "limit": 20
}
```

Key mappings: VISUALIZE → `calculations` (each with `op` and optional `column`), WHERE → `filters` (each with `column`, `op`, `value`), GROUP BY → `breakdowns` (array of column names), ORDER BY → `orders` (with `order`: `"descending"` or `"ascending"`), LIMIT → `limit`.

See `references/query-examples.md` for a full catalog of queries in `query_spec` format.

## VISUALIZE Operations (Quick Reference)

| Operation | Use When |
|-----------|----------|
| `COUNT` | Counting events (requests, errors, spans) |
| `COUNT_DISTINCT(field)` | Unique values (users, IPs, trace IDs) |
| `SUM(field)` | Totals (bytes, cost, items processed) |
| `AVG(field)` | Average values (payload size) — **never use for latency** |
| `P50/P90/P95/P99(field)` | Latency percentiles (use instead of AVG for latency) |
| `MAX(field)` / `MIN(field)` | Extremes (worst case latency, minimum throughput) |
| `HEATMAP(field)` | Distribution visualization (latency spread, bimodal detection) |
| `RATE_AVG/RATE_SUM(field)` | Rate of change over time |
| `CONCURRENCY` | Concurrent overlapping operations |

For the full list with detailed descriptions, consult `references/visualize-operations.md`.

## Filter Operators

| Operator | Meaning | Value Type |
|----------|---------|------------|
| `=`, `!=` | Equals / not equals | string, number, boolean |
| `>`, `>=`, `<`, `<=` | Comparison | number |
| `exists`, `does-not-exist` | Field presence | (no value) |
| `contains`, `does-not-contain` | Substring match | string |
| `starts-with`, `does-not-start-with` | Prefix match | string |
| `ends-with`, `does-not-end-with` | Suffix match | string |
| `in`, `not-in` | Set membership | array |
| `search` | Full-text search | array of terms |

## Relational Field Prefixes

Trace-aware queries use prefixes to query across span relationships:

| Prefix | Matches | Returns |
|--------|---------|---------|
| `root.` | Root span of the trace | The matched root span |
| `parent.` | Direct parent span | The child span |
| `child.` | Direct child span | The parent span |
| `any.` / `any2.` / `any3.` | Any span in the trace | The span being evaluated |
| `none.` | Excludes traces with match | Spans from non-matching traces |

**Common patterns** (Query Builder notation — see `references/relational-fields.md` for `query_spec` format):
- Find slow API calls: `WHERE root.http.route = "/api/checkout" VISUALIZE P99(duration_ms) GROUP BY name`
- Cross-service errors: `WHERE any.service.name = "payment-service" AND any.error = true`
- Missing instrumentation: `WHERE none.trace.parent_id does-not-exist`

For comprehensive relational field examples, consult `references/relational-fields.md`.

## Inline Calculated Fields

Create derived columns within a query using the `calculated_fields` parameter:

```
calculated_fields: [
  { name: "is_error", expression: "GTE($http.status_code, 400)" },
  { name: "is_slow", expression: "GTE($duration_ms, 1000)" }
]
```

Available functions: `LT`, `LTE`, `GT`, `GTE`, `EQUALS`, `IN`, `AND`, `OR`, `NOT`,
`IF`, `EXISTS`, `COALESCE`, `SUM`, `SUB`, `MUL`, `DIV`, `MOD`, `MIN`, `MAX`,
`CONCAT`, `LENGTH`, `CONTAINS`, `STARTS_WITH`, `TO_LOWER`, `REG_MATCH`, `REG_VALUE`,
`INT`, `FLOAT`, `STRING`, `BOOL`, `BUCKET`, `UNIX_TIMESTAMP`, `FORMAT_TIME`.

Expression functions (GTE, LTE, etc.) are ONLY valid inside calculated field expressions,
NOT as filter operators. Filters use symbols (`>=`, `<=`).

## Common Query Patterns

> These examples use Honeycomb Query Builder notation. See [Translating to run_query](#translating-to-run_query) above and `references/query-examples.md` for `query_spec` JSON equivalents.

### Performance
- Slowest endpoints: `VISUALIZE P99(duration_ms) WHERE is_root GROUP BY http.route`
- Database bottlenecks: `VISUALIZE P90(duration_ms) WHERE db.system exists GROUP BY db.statement, service.name`

### Errors
- Error rate by service: `VISUALIZE COUNT WHERE error = true GROUP BY service.name`
- Exception breakdown: `VISUALIZE COUNT WHERE exception.message exists GROUP BY exception.message`

### Traffic
- Request volume: `VISUALIZE COUNT WHERE is_root GROUP BY http.route`
- Unique users: `VISUALIZE COUNT_DISTINCT(user.id) WHERE is_root`

For a full catalog, consult `references/query-examples.md`.

## Working with Boards

**Creating boards** with `create_board`:
- Add query results by passing query run PKs (format: `QR-abc123`)
- Add SLOs by passing SLO PKs (format: `SLO-abc123`)
- Add text panels with Markdown content
- Apply tags in `key:value` format for organization
- Board layout: queries occupy 4 grid units (3 per row), SLOs occupy 3 units (4 per row)

**Finding boards** with `list_boards`:
- List all boards in an environment
- Retrieve a specific board by ID
- Filter by tags

**Limitation**: MCP can create new boards but cannot add queries to existing boards. Use the Honeycomb UI for that.

## Prompting Best Practices

1. **Prime context first** — Call `get_workspace_context`, then `find_columns`
2. **Check for prior work** — Call `find_queries` to see if relevant queries exist
3. **Be specific about scope** — Specify environment slug, dataset slug, and time range
4. **Use human-readable time** — `"24h"`, `"7d"`, `"-2h"` (not epoch timestamps)
5. **Start broad, narrow down** — Begin with COUNT/GROUP BY, then add WHERE filters
6. **Use HEATMAP for distributions** — Reveals bimodal patterns invisible in single numbers
7. **Prefer percentiles over averages** — P99 reveals tail latency that AVG hides
8. **Combine operations** — `VISUALIZE COUNT, P99(duration_ms), HEATMAP(duration_ms)` in one query

## Additional Resources

### Reference Files
- **`references/visualize-operations.md`** — Complete VISUALIZE operation reference with examples
- **`references/relational-fields.md`** — Detailed relational field guide with cross-service patterns
- **`references/query-examples.md`** — Extensive query cookbook organized by use case
