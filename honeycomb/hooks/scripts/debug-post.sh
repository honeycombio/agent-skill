#!/usr/bin/env bash
# Debug: just log whatever the hook receives
input=$(cat)
echo "$input" > /tmp/honeycomb-hook-debug.json
exit 0
