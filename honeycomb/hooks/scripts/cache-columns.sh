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
tool_result=$(echo "$input" | jq -r '.tool_result // empty')

# All fields required — fail open if anything is missing
if [[ -z "$env_slug" || -z "$dataset_slug" || -z "$tool_result" ]]; then
  exit 0
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

exit 0
