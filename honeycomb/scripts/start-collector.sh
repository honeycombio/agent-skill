#!/usr/bin/env bash
# Starts an OTel Collector via Docker.
#
# Usage:
#   ./scripts/start-collector.sh [--config <path>] [--api-key <key>] [--log-file <path>]
#
#   --config    Path to a collector config YAML file. Defaults to a built-in
#               Honeycomb config that reads HONEYCOMB_API_KEY from the environment.
#   --api-key   Honeycomb API key. Overrides the HONEYCOMB_API_KEY env var.
#   --log-file     Path for the span log file (default: ./otelcol-spans.ndjson).
#                  Only used with the default config; ignored when --config is supplied.
#   --no-honeycomb Skip the Honeycomb exporter; use only debug (stdout) and file exporters.
#                  API key is not required when this flag is set.
#
# Examples:
#   HONEYCOMB_API_KEY=abc123 ./scripts/start-collector.sh
#   ./scripts/start-collector.sh --api-key abc123 --log-file /tmp/spans.ndjson
#   ./scripts/start-collector.sh --no-honeycomb
#   ./scripts/start-collector.sh --config ./my-collector-config.yaml

set -euo pipefail

COLLECTOR_IMAGE="otel/opentelemetry-collector-contrib:latest"
CONTAINER_NAME="otel-collector"
GRPC_PORT=4317
HTTP_PORT=4318

CONFIG_PATH=""
API_KEY="${HONEYCOMB_API_KEY:-}"
LOG_FILE="./otelcol-spans.ndjson"
NO_HONEYCOMB=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)       CONFIG_PATH="$2"; shift 2 ;;
    --api-key)      API_KEY="$2";     shift 2 ;;
    --log-file)     LOG_FILE="$2";    shift 2 ;;
    --no-honeycomb) NO_HONEYCOMB=true; shift ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# Build a temporary default config if none was provided
TEMP_CONFIG=""
LOG_FILE_ABS=""
if [[ -z "$CONFIG_PATH" ]]; then
  if [[ "$NO_HONEYCOMB" == false && -z "$API_KEY" ]]; then
    echo "Error: supply --api-key, set HONEYCOMB_API_KEY, or use --no-honeycomb" >&2
    exit 1
  fi

  # Resolve the log file to an absolute path and ensure it exists so Docker
  # bind-mounts a file rather than creating a directory.
  LOG_FILE_ABS="$(cd "$(dirname "$LOG_FILE")" && pwd)/$(basename "$LOG_FILE")"
  touch "$LOG_FILE_ABS"

  TEMP_CONFIG="$(mktemp /tmp/otelcol-config.XXXXXX.yaml)"

  if [[ "$NO_HONEYCOMB" == true ]]; then
    cat > "$TEMP_CONFIG" <<YAML
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: "0.0.0.0:4317"
      http:
        endpoint: "0.0.0.0:4318"

processors:
  batch:
    timeout: 1s
    send_batch_size: 1024

exporters:
  debug:
    verbosity: detailed
  file:
    path: /tmp/otel-spans.ndjson

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [debug, file]
YAML
  else
    cat > "$TEMP_CONFIG" <<YAML
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: "0.0.0.0:4317"
      http:
        endpoint: "0.0.0.0:4318"

processors:
  batch:
    timeout: 1s
    send_batch_size: 1024

exporters:
  otlp/honeycomb:
    endpoint: "api.honeycomb.io:443"
    headers:
      x-honeycomb-team: "${API_KEY}"
  debug:
    verbosity: detailed
  file:
    path: /tmp/otel-spans.ndjson

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp/honeycomb, debug, file]
YAML
  fi
  CONFIG_PATH="$TEMP_CONFIG"
fi

cleanup() {
  echo ""
  echo "Stopping collector..."
  docker stop "$CONTAINER_NAME" 2>/dev/null || true
  if [[ -n "$TEMP_CONFIG" ]]; then
    rm -f "$TEMP_CONFIG"
  fi
}
trap cleanup EXIT INT TERM

# Remove any previous container with the same name
docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

CONFIG_ABS="$(cd "$(dirname "$CONFIG_PATH")" && pwd)/$(basename "$CONFIG_PATH")"

echo "Starting OTel Collector (image: $COLLECTOR_IMAGE)"
echo "  Config : $CONFIG_ABS"
echo "  gRPC   : localhost:$GRPC_PORT"
echo "  HTTP   : localhost:$HTTP_PORT"
if [[ -n "$LOG_FILE_ABS" ]]; then
  echo "  Log    : $LOG_FILE_ABS"
fi
echo ""

LOG_MOUNT_ARGS=()
if [[ -n "$LOG_FILE_ABS" ]]; then
  LOG_MOUNT_ARGS=(-v "${LOG_FILE_ABS}:/tmp/otel-spans.ndjson")
fi

docker run \
  --name "$CONTAINER_NAME" \
  --rm \
  -p "${GRPC_PORT}:4317" \
  -p "${HTTP_PORT}:4318" \
  -v "${CONFIG_ABS}:/etc/otelcol/config.yaml:ro" \
  "${LOG_MOUNT_ARGS[@]+"${LOG_MOUNT_ARGS[@]}"}" \
  "$COLLECTOR_IMAGE" \
  --config /etc/otelcol/config.yaml
