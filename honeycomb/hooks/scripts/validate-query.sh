#!/usr/bin/env bash
set -euo pipefail

# PreToolUse hook for run_query.
#
# Validates column names in the query_spec against the schema cache built
# by cache-columns.sh and emits an advisory systemMessage for any column not
# present. It never blocks the query (never returns permissionDecision: deny):
# the Honeycomb API is the authoritative validator, and this client-side cache
# can be stale (columns arriving mid-session), incomplete (get_dataset_columns
# pagination), or blind to query-only identifiers we don't model — so a hard
# deny would risk blocking a valid query the API would accept. Cache
# completeness only tunes how firm the nudge is:
#
#   No cache for this dataset      → systemMessage nudge (soft)
#   Partial cache, column missing  → systemMessage nudge (soft)
#   Complete cache, column missing → systemMessage nudge (firm)
#
# Nudges include fuzzy-match suggestions via Python's difflib so the model
# can self-correct without a round-trip to the API.

input=$(cat)

env_slug=$(echo "$input" | jq -r '.tool_input.environment_slug // empty')
dataset_slug=$(echo "$input" | jq -r '.tool_input.dataset_slug // empty')
session_id=$(echo "$input" | jq -r '.session_id // "default"')
query_spec=$(echo "$input" | jq -c '.tool_input.query_spec // empty')

# Can't validate without these — fail open
if [[ -z "$env_slug" || -z "$dataset_slug" || -z "$query_spec" ]]; then
  exit 0
fi

# ── Well-known columns ────────────────────────────────────────────────
# Structural columns present in virtually every Honeycomb dataset.
# These pass validation even when not in the cache.
WELLKNOWN=(
  "duration_ms"
  "trace.trace_id"
  "trace.span_id"
  "trace.parent_id"
  "error"
  "name"
  "service.name"
  "is_root"
)

is_wellknown() {
  local col="$1"
  for wk in "${WELLKNOWN[@]}"; do
    [[ "$col" == "$wk" ]] && return 0
  done
  return 1
}

# ── Relational prefix stripping ───────────────────────────────────────
# Columns like any.service.name or root.http.route use query-time prefixes
# that aren't part of the actual column name.
strip_relational_prefix() {
  echo "$1" | sed -E 's/^(any|root|none|parent|child)\.//'
}

# ── Extract column references from query_spec ─────────────────────────
# Pulls column names from calculations, filters, breakdowns, and orders,
# then subtracts query-local names (named calculations, formulas,
# calculated fields) which are valid references but not dataset columns.
columns=$(echo "$query_spec" | jq -r '
  # Names defined within the query itself — not dataset columns
  (
    [
      (.calculations // [] | map(select(.name != null) | .name)),
      (.formulas // [] | map(select(.name != null) | .name)),
      (.calculated_fields // [] | map(select(.name != null) | .name))
    ] | flatten
  ) as $local_names |
  [
    (.calculations // [] | map(select(.column != null) | .column)),
    (.filters // [] | map(select(.column != null) | .column)),
    (.breakdowns // []),
    (.orders // [] | map(select(.column != null) | .column))
  ] | flatten | unique | map(select(. as $c | $local_names | index($c) | not)) | .[]
' 2>/dev/null) || exit 0

if [[ -z "$columns" ]]; then
  exit 0
fi

# ── Check for cached schema ───────────────────────────────────────────
cache_dir="${TMPDIR:-/tmp}/honeycomb-schema/${session_id}"
cache_file="${cache_dir}/${env_slug}--${dataset_slug}.txt"
cache_file_all="${cache_dir}/${env_slug}--_all.txt"

# Try dataset-specific cache first, then cross-dataset cache
if [[ ! -f "$cache_file" ]]; then
  if [[ -f "$cache_file_all" ]]; then
    cache_file="$cache_file_all"
  else
    # No cache — soft nudge, don't block
    jq -n --arg dataset "$dataset_slug" '{
      systemMessage: "Column names for dataset \"\($dataset)\" have not been validated this session. Consider calling find_columns or get_dataset_columns for this dataset first to avoid unknown column errors."
    }'
    exit 0
  fi
fi

# ── Check cache completeness ─────────────────────────────────────────
# A .complete marker means the cache was built from get_dataset_columns
# (which returns ALL columns). Without it, the cache is partial (from
# find_columns top-50) and we should soft-nudge instead of hard-deny.
complete_marker="${cache_file%.txt}.complete"
cache_is_complete=false
if [[ -f "$complete_marker" ]]; then
  cache_is_complete=true
fi

# ── Validate each column ──────────────────────────────────────────────
unknown=()
suggestions=()

while IFS= read -r col; do
  [[ -z "$col" ]] && continue

  # Strip relational prefix for validation
  bare_col=$(strip_relational_prefix "$col")

  # Skip well-known columns
  if is_wellknown "$bare_col"; then
    continue
  fi

  # Check cache (exact match)
  if grep -qxF "$bare_col" "$cache_file" 2>/dev/null; then
    continue
  fi

  # Column not found
  unknown+=("$col")

  # Fuzzy match via Python difflib
  matches=$(python3 -c "
import difflib, sys
col = sys.argv[1]
known = [l.strip() for l in open(sys.argv[2]) if l.strip()]
matches = difflib.get_close_matches(col, known, n=3, cutoff=0.4)
print(', '.join(matches) if matches else '')
" "$bare_col" "$cache_file" 2>/dev/null) || matches=""

  if [[ -n "$matches" ]]; then
    suggestions+=("${col} -> maybe: ${matches}")
  else
    suggestions+=("${col} -> no close matches in cached schema")
  fi
done <<< "$columns"

# All columns valid
if [[ ${#unknown[@]} -eq 0 ]]; then
  exit 0
fi

# ── Build response ───────────────────────────────────────────────────
# Always advisory: emit a systemMessage, never a permissionDecision deny.
# The API is the source of truth for column validity; this cache can be
# stale, incomplete (pagination), or blind to query-only identifiers, so a
# hard deny would block valid queries the API would accept — worse than the
# cheap, self-correcting API error it tries to save. Cache completeness only
# tunes how firmly we phrase the nudge.
unknown_str=$(printf '%s, ' "${unknown[@]}" | sed 's/, $//')
suggestion_str=$(printf '%s\n' "${suggestions[@]}")

if [[ "$cache_is_complete" == "true" ]]; then
  # Complete cache (from get_dataset_columns) — firm nudge
  jq -n \
    --arg cols "$unknown_str" \
    --arg hints "$suggestion_str" \
    --arg dataset "$dataset_slug" \
    '{
      systemMessage: "Column names not found in the cached schema for dataset \"\($dataset)\" (cache built from get_dataset_columns): [\($cols)]. These are likely typos or wrong names — verify or fix them before relying on the results.\nSuggestions:\n\($hints)\nCall get_dataset_columns to refresh the schema cache, or find_columns to search for correct column names. The query is not blocked; the Honeycomb API is the source of truth."
    }'
else
  # Partial cache (from find_columns) — soft nudge
  jq -n \
    --arg cols "$unknown_str" \
    --arg hints "$suggestion_str" \
    --arg dataset "$dataset_slug" \
    '{
      systemMessage: "Column names not yet verified for dataset \"\($dataset)\": [\($cols)]. The schema cache is incomplete (built from find_columns, not get_dataset_columns). These columns may exist but were not in the top results.\nSuggestions:\n\($hints)\nConsider calling get_dataset_columns to build a complete cache, or verify these column names are correct."
    }'
fi

exit 0
