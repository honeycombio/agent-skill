#!/usr/bin/env bash
set -euo pipefail

# PreToolUse hook for run_query.
#
# Validates column names in the query_spec against the schema cache built
# by cache-columns.sh. Two modes:
#
#   No cache for this dataset → systemMessage nudge (soft)
#   Cache exists, column missing → permissionDecision: deny (hard)
#
# Denials include fuzzy-match suggestions via Python's difflib so the model
# can self-correct without a round-trip to the API.

input=$(cat)

env_slug=$(echo "$input" | jq -r '.tool_input.environment_slug // empty')
dataset_slug=$(echo "$input" | jq -r '.tool_input.dataset_slug // empty')
session_id=$(echo "$input" | jq -r '.session_id // "default"')
query_spec=$(echo "$input" | jq -r '.tool_input.query_spec // empty')

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
# Pulls column names from calculations, filters, breakdowns, and orders.
columns=$(echo "$query_spec" | jq -r '
  [
    (.calculations // [] | map(select(.column != null) | .column)),
    (.filters // [] | map(select(.column != null) | .column)),
    (.breakdowns // []),
    (.orders // [] | map(select(.column != null) | .column))
  ] | flatten | unique | .[]
' 2>/dev/null) || exit 0

if [[ -z "$columns" ]]; then
  exit 0
fi

# ── Check for cached schema ───────────────────────────────────────────
cache_dir="${TMPDIR:-/tmp}/honeycomb-schema/${session_id}"
cache_file="${cache_dir}/${env_slug}--${dataset_slug}.txt"

if [[ ! -f "$cache_file" ]]; then
  # No cache — soft nudge, don't block
  jq -n --arg dataset "$dataset_slug" '{
    systemMessage: "Column names for dataset \"\($dataset)\" have not been validated this session. Consider calling find_columns or get_dataset_columns for this dataset first to avoid unknown column errors."
  }'
  exit 0
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

# ── Build deny response ──────────────────────────────────────────────
unknown_str=$(printf '%s, ' "${unknown[@]}" | sed 's/, $//')
suggestion_str=$(printf '%s\n' "${suggestions[@]}")

jq -n \
  --arg cols "$unknown_str" \
  --arg hints "$suggestion_str" \
  --arg dataset "$dataset_slug" \
  '{
    hookSpecificOutput: {
      permissionDecision: "deny"
    },
    systemMessage: "Query references columns not found in cached schema for \"\($dataset)\": [\($cols)].\nSuggestions:\n\($hints)\nCall find_columns to discover correct column names before retrying."
  }'

exit 0
