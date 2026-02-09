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

Opinionated guidance for writing effective Honeycomb queries. The MCP tools already
document their parameters and schemas — this skill focuses on *when* and *why* to
use each pattern, not *how* to call the tools.

## Key Principles

1. **Never use AVG for latency** — AVG hides tail latency. Use P99 (or P95/P90) to see what slow users experience. Reserve AVG for non-latency metrics like payload size.
2. **Use HEATMAP for distributions** — Single-number aggregates hide bimodal patterns. HEATMAP reveals whether you have one population or two.
3. **Combine calculations in one query** — `COUNT, P99(duration_ms), HEATMAP(duration_ms)` in a single query reduces API calls and gives a complete picture.
4. **Start broad, narrow with WHERE** — Begin with a COUNT/GROUP BY to understand shape, then add filters to focus.
5. **Check for prior work** — Call `find_queries` before writing new queries. Someone may have already answered the question.

## Choosing the Right Operation

| Question | Use |
|----------|-----|
| How much traffic? | `COUNT` grouped by route or service |
| How many unique users/IPs? | `COUNT_DISTINCT(field)` |
| How fast for most users? | `P50(duration_ms)` |
| How fast for the worst-off users? | `P99(duration_ms)` |
| Is there a bimodal pattern? | `HEATMAP(duration_ms)` |
| What's the worst case? | `MAX(duration_ms)` |
| How many concurrent operations? | `CONCURRENCY` |
| Is it getting worse over time? | `RATE_AVG(duration_ms)` |

## Relational Field Strategy

Use relational prefixes to ask cross-span questions within a trace:

- **"Show me slow endpoints caused by a specific downstream"**: Filter with `any.service.name` to find traces where that service participates, group by `root.http.route` to see which user-facing endpoints are affected.
- **"What's different about errored traces?"**: Filter with `any.error = true`, group by `root.name` to see which entry points have errors somewhere in their trace tree.
- **Exclude noise**: `none.service.name = "health-check"` removes traces containing health checks.

## Calculated Fields: When to Use

Use inline calculated fields to create boolean columns for filtering and grouping:
- **Error classification**: `GTE($http.status_code, 500)` for server errors vs `GTE($http.status_code, 400)` for all errors
- **Latency bucketing**: `BUCKET($duration_ms, 100)` to create 100ms buckets
- **Business logic**: `EQUALS($checkout.status, "completed")` for success rate

These are expression functions for calculated fields only — don't confuse with filter operators (which use `=`, `>=`, etc.).

## Common Mistakes

- Using `AVG(duration_ms)` for latency (hides P99 problems)
- Forgetting to filter `is_root` when measuring user-facing latency (includes internal spans)
- Using epoch timestamps instead of human-readable time ranges (`"24h"`, `"-6h"`)
- Querying without checking columns first (leads to empty results or wrong field names)
- Creating separate queries when one multi-calculation query would suffice

## Additional Resources

### Reference Files
- **`references/visualize-operations.md`** — Complete VISUALIZE operation reference with examples
- **`references/relational-fields.md`** — Detailed relational field guide with cross-service patterns
- **`references/query-examples.md`** — Extensive query cookbook organized by use case
