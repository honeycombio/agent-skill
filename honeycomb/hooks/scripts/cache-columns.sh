#!/usr/bin/env bash
set -euo pipefail

# PostToolUse hook for find_columns / get_dataset_columns.
#
# Caches column names from the tool result into a per-session temp file.
# The validate-query.sh PreToolUse hook checks this cache before run_query
# to catch unknown column names before they hit the API.
#
# Cache location: $TMPDIR/honeycomb-schema/$session_id/$env--$dataset.txt
# One column name per line, sorted and deduplicated.

input=$(cat)

env_slug=$(echo "$input" | jq -r '.tool_input.environment_slug // empty')
dataset_slug=$(echo "$input" | jq -r '.tool_input.dataset_slug // empty')
session_id=$(echo "$input" | jq -r '.session_id // "default"')
tool_name=$(echo "$input" | jq -r '.tool_name // empty')
tool_result=$(echo "$input" | jq -r '.tool_response[0].text // empty')

# Environment and result required — fail open if missing
if [[ -z "$env_slug" || -z "$tool_result" ]]; then
  exit 0
fi

# If no dataset specified, use "_all" as a cross-dataset cache
if [[ -z "$dataset_slug" ]]; then
  dataset_slug="_all"
fi

cache_dir="${TMPDIR:-/tmp}/honeycomb-schema/${session_id}"
mkdir -p "$cache_dir"
cache_file="${cache_dir}/${env_slug}--${dataset_slug}.txt"

# Parse column names from markdown table output.
# Both find_columns and get_dataset_columns return pipe-delimited tables
# with the column name in the first data column:
#   | Name | Type | Description | ...
#   |------|------|-------------|
#   | app.team_id | integer | ... |
#
# Strategy: grab rows with pipes, skip the header and separator,
# extract the first data cell.
echo "$tool_result" \
  | grep -E '^\s*\|' \
  | grep -vE '^\s*\|\s*Name\s*\|' \
  | grep -vE '^\s*\|\s*-' \
  | awk -F'|' '{gsub(/^[ \t]+|[ \t]+$/, "", $2); if ($2 != "" && $2 !~ /^[- ]+$/) print $2}' \
  >> "$cache_file" 2>/dev/null || true

# Deduplicate
if [[ -f "$cache_file" ]]; then
  sort -u "$cache_file" -o "$cache_file"
fi

# Mark the cache "complete" only when we actually hold the FULL schema.
# find_columns returns only its top-N matches, so its cache is always partial
# (no marker). get_dataset_columns paginates: one response is the whole schema
# only when total_pages <= 1; for multi-page schemas we record which pages we've
# cached and mark complete once every page has been seen. validate-query.sh keys
# its nudge firmness off this marker, so marking complete while pages are still
# un-fetched would nudge against columns that genuinely exist on later pages.
if [[ "$tool_name" == *get_dataset_columns* ]]; then
  # `page:` is anchored to line-start so it doesn't also match `items_per_page:`.
  total_pages=$(printf '%s\n' "$tool_result" | grep -E '^[[:space:]]*total_pages:[[:space:]]*[0-9]+' | grep -oE '[0-9]+' | head -1 || true)
  page=$(printf '%s\n' "$tool_result" | grep -E '^[[:space:]]*page:[[:space:]]*[0-9]+' | grep -oE '[0-9]+' | head -1 || true)
  : "${total_pages:=1}"
  : "${page:=1}"

  complete_marker="${cache_file%.txt}.complete"
  if [[ "$total_pages" -le 1 ]]; then
    # Single page is the entire schema.
    touch "$complete_marker"
  else
    # Multi-page: track distinct pages seen; complete once all are cached.
    pages_file="${cache_file%.txt}.pages"
    echo "$page" >> "$pages_file"
    sort -un "$pages_file" -o "$pages_file"
    seen=$(wc -l < "$pages_file" | tr -d '[:space:]')
    if [[ "$seen" -ge "$total_pages" ]]; then
      touch "$complete_marker"
    fi
  fi
fi

exit 0
