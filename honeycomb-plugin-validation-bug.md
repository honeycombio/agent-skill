# Honeycomb Plugin: Query Validation Hook Bug Report

## Summary

The `validate-query.sh` pre-tool-use hook in the Honeycomb Claude Code plugin (v1.7.0) blocks valid queries by rejecting column names that exist in the dataset but weren't returned by `find_columns` during the session. It also incorrectly treats formula names and named calculation references as column names.

## Status

- **Bug 2 & 3: FIXED** in PR #5 (`fix/v1.7.0-test-failures` branch)
- **Bug 1: FIXED** — partial caches (from `find_columns`) now soft-nudge instead of hard-deny

## Tests

`tests/structural/test_validate_query_hook.py` — 38 tests covering the hook end-to-end via subprocess. Key test classes:

| Class | What it covers |
|-------|---------------|
| `TestFailOpen` | Missing fields → silent exit |
| `TestNoCacheNudge` | No cache → soft systemMessage nudge |
| `TestDenyUnknownColumns` | Cache exists, column missing → hard deny with fuzzy suggestions |
| `TestValidColumns` | All columns in cache → silent pass |
| `TestWellKnownColumns` | 8 well-known columns always pass (parametrized) |
| `TestRelationalPrefixes` | any/root/none/parent/child prefix stripping (parametrized) |
| `TestAllDatasetFallback` | `_all` cache fallback, dataset-specific takes priority |
| `TestColumnExtraction` | Columns from calculations, filters, breakdowns, orders |
| `TestNamedCalculationsInOrders` | Bug 2 fix: named calcs and formulas in orders |
| `TestCalculatedFields` | Bug 3 fix: calculated field names in breakdowns/filters/calcs |
| `TestPartialCacheNudge` | Bug 1 fix: partial cache soft-nudges, complete cache hard-denies |

Helper functions `_run_hook()`, `_make_input()`, `_write_cache()` handle the subprocess plumbing and cache setup. Tests use `tempfile.TemporaryDirectory` with `TMPDIR` override to isolate cache state.

## Plugin Location

formerly Installed at:
```
/Users/jessitron/.claude/plugins/cache/honeycomb-plugins/honeycomb/1.7.0/
```

it's in the honeycombio/agent-skill repo

Hook config: `hooks/hooks.json`
Validation script: `hooks/scripts/validate-query.sh`
Cache script: `hooks/scripts/cache-columns.sh`

## How It Works

1. **PostToolUse** on `find_columns` / `get_dataset_columns` / `get_dataset`: `cache-columns.sh` saves returned column names to `/tmp/honeycomb-schema/{session}/{env}--{dataset}.txt`.
2. **PreToolUse** on `run_query`: `validate-query.sh` extracts every column reference from the query spec and checks it against the cache. Unknown columns get a hard **deny**.

## Bug 1: Incomplete Schema Cache — FIXED

**Fixed in:** commit `3af4bda`, using option 1 (track cache completeness).

`find_columns` returns at most 50 results, ranked by relevance to the search terms. Columns that exist in the dataset but don't rank in the top 50 never enter the cache. The hook now distinguishes partial caches from complete ones.

**How the fix works:**
- `cache-columns.sh` reads `tool_name` from the hook input. When the tool is `get_dataset_columns` (returns ALL columns), it writes a `.complete` marker file alongside the cache.
- `validate-query.sh` checks for the `.complete` marker. Complete cache → hard deny. Partial cache (no marker) → soft `systemMessage` nudge with column names and fuzzy suggestions.

## Bug 2: Formula/Calculation Names Treated as Columns — FIXED

**Fixed in:** PR #5, commit `78d82a7`

The jq column extractor now collects "query-local names" from `calculations[].name`, `formulas[].name`, and `calculated_fields[].name` and filters them out before validation. The fix is entirely within the jq expression in `validate-query.sh` lines 58-75.

## Bug 3: Calculated Fields Output Names Rejected — FIXED

**Fixed in:** Same commit as Bug 2 — same root cause, same fix.

## Columns Blocked During This Session

| Column | Exists in data? | Why blocked |
|--------|----------------|-------------|
| `meta.signal_type` | No | Legitimately blocked (good catch!) |
| `http.route` | Yes (sample: `/product/{id}`) | Not in top-50 find_columns results |
| `http.status_code` | Yes (sample: `200`, `302`, `500`) | Not in top-50 find_columns results |
| `app.user_id` | Yes (sample: `20109`, `70702`) | Not in top-50 find_columns results |
| `error_pct` | N/A (calculated_field) | Hook doesn't understand calculated_fields |
| `error_rate` | N/A (formula name) | Hook doesn't understand formulas |
| `total` | N/A (named calculation) | Hook doesn't understand named calculations |

Note: `meta.signal_type` was correctly blocked — it genuinely doesn't exist in this dataset. That's the hook working as intended.

## Workarounds Used

- Replaced `http.route` with `name` (the span name field, which has route patterns)
- Replaced `http.status_code` with `status_code` (OTel status code, not HTTP — different semantics)
- Used compound queries with per-calculation filters instead of calculated_fields
- Ordered by breakdown fields instead of formula/calculation names
- Dropped the user-id breakdown query entirely
