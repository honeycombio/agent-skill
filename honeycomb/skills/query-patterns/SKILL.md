---
name: query-patterns
description: >
  This skill provides opinionated query construction and result interpretation
  for Honeycomb — which operations to use (percentiles not AVG for latency,
  HEATMAP for distributions), how to combine calculations, relational field
  patterns, and how to interpret results (P99/P50 ratios, heatmap bands,
  TOTAL/OTHER rows, raw JSON via query_result_json). This skill should be loaded
  before calling run_query. Trigger phrases: "show me latency", "what's the error rate",
  "find slow requests", "show me the distribution", "query Honeycomb",
  "find outliers", "search traces", "why is latency high",
  "why are some requests slow", "what does this result mean",
  "explain the heatmap", "interpret these numbers", "is it getting worse",
  "compare before and after", "find fields", "discover columns",
  "look at past queries", "query across services", "use relational fields",
  "download raw results", or any request to query, visualize, or interpret
  Honeycomb data.
metadata:
  version: "1.2.0"
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

## Interpreting Results

After running a query, the MCP tool returns formatted markdown plus metadata.
The most important metadata field is `query_result_json` — a signed URL to the raw
JSON result. For precise analysis, download it and parse with jq or python rather
than relying solely on the ASCII rendering.

Key interpretation rules:
- **P99/P50 > 10x** — bimodal distribution likely; run HEATMAP to confirm
- **TOTAL row** in breakdown results = aggregate across all groups
- **OTHER row** = groups beyond the query limit (increase limit if OTHER is large)
- **ASCII heatmap** `▁▂▃▄▅▆▇█` = density from low to high; two bands = two populations
- **query_run_pk** in metadata — feed directly to `run_bubbleup` for outlier analysis

## Additional Resources

### Reference Files
- **`${CLAUDE_PLUGIN_ROOT}/skills/query-patterns/references/visualize-operations.md`** — Complete VISUALIZE operation reference with examples
- **`${CLAUDE_PLUGIN_ROOT}/skills/query-patterns/references/relational-fields.md`** — Detailed relational field guide with cross-service patterns
- **`${CLAUDE_PLUGIN_ROOT}/skills/query-patterns/references/query-examples.md`** — Extensive query cookbook organized by use case
- **`${CLAUDE_PLUGIN_ROOT}/skills/query-patterns/references/result-interpretation.md`** — Guide to interpreting query results, raw JSON access, and statistical heuristics
