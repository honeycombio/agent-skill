#!/usr/bin/env bash
# Starts an OTel Collector via Docker.
#
# Usage:
#   ./scripts/start-collector.sh [--config <path>] [--api-key <key>]
#                                [--traces-file <path>] [--logs-file <path>] [--metrics-file <path>]
#                                [--no-honeycomb]
#
#   --config        Path to a collector config YAML file. Defaults to a built-in
#                   Honeycomb config that reads HONEYCOMB_API_KEY from the environment.
#   --api-key       Honeycomb API key. Overrides the HONEYCOMB_API_KEY env var.
#   --traces-file   Host path for the traces NDJSON log (default: ./otelcol-traces.ndjson).
#   --logs-file     Host path for the logs NDJSON log   (default: ./otelcol-logs.ndjson).
#   --metrics-file  Host path for the metrics NDJSON log (default: ./otelcol-metrics.ndjson).
#                   File flags are only used with the default config; ignored when --config is supplied.
#   --no-honeycomb  Skip the Honeycomb exporter; use only debug (stdout) and file exporters.
#                   API key is not required when this flag is set.
#
# Examples:
#   HONEYCOMB_API_KEY=abc123 ./scripts/start-collector.sh
#   ./scripts/start-collector.sh --api-key abc123
#   ./scripts/start-collector.sh --no-honeycomb
#   ./scripts/start-collector.sh --no-honeycomb --traces-file /tmp/traces.ndjson
#   ./scripts/start-collector.sh --config ./my-collector-config.yaml

set -euo pipefail

COLLECTOR_IMAGE="otel/opentelemetry-collector-contrib:latest"
CONTAINER_NAME="otel-collector"
GRPC_PORT=4317
HTTP_PORT=4318

CONFIG_PATH=""
API_KEY="${HONEYCOMB_API_KEY:-}"
TRACES_FILE="./otelcol-traces.ndjson"
LOGS_FILE="./otelcol-logs.ndjson"
METRICS_FILE="./otelcol-metrics.ndjson"
NO_HONEYCOMB=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)        CONFIG_PATH="$2"; shift 2 ;;
    --api-key)       API_KEY="$2";     shift 2 ;;
    --traces-file)   TRACES_FILE="$2"; shift 2 ;;
    --logs-file)     LOGS_FILE="$2";   shift 2 ;;
    --metrics-file)  METRICS_FILE="$2"; shift 2 ;;
    --no-honeycomb)  NO_HONEYCOMB=true; shift ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# Resolve a path to absolute and touch the file so Docker bind-mounts a file,
# not a directory.
resolve_log_file() {
  local path="$1"
  local abs
  abs="$(cd "$(dirname "$path")" && pwd)/$(basename "$path")"
  touch "$abs"
  echo "$abs"
}

# Build a temporary default config if none was provided
TEMP_CONFIG=""
TRACES_FILE_ABS=""
LOGS_FILE_ABS=""
METRICS_FILE_ABS=""
if [[ -z "$CONFIG_PATH" ]]; then
  if [[ "$NO_HONEYCOMB" == false && -z "$API_KEY" ]]; then
    echo "Error: supply --api-key, set HONEYCOMB_API_KEY, or use --no-honeycomb" >&2
    exit 1
  fi

  TRACES_FILE_ABS="$(resolve_log_file "$TRACES_FILE")"
  LOGS_FILE_ABS="$(resolve_log_file "$LOGS_FILE")"
  METRICS_FILE_ABS="$(resolve_log_file "$METRICS_FILE")"

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
  file/traces:
    path: /tmp/otel-traces.ndjson
  file/logs:
    path: /tmp/otel-logs.ndjson
  file/metrics:
    path: /tmp/otel-metrics.ndjson

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [debug, file/traces]
    logs:
      receivers: [otlp]
      processors: [batch]
      exporters: [debug, file/logs]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [debug, file/metrics]
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
  file/traces:
    path: /tmp/otel-traces.ndjson
  file/logs:
    path: /tmp/otel-logs.ndjson
  file/metrics:
    path: /tmp/otel-metrics.ndjson

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp/honeycomb, debug, file/traces]
    logs:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp/honeycomb, debug, file/logs]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp/honeycomb, debug, file/metrics]
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
echo "  Config  : $CONFIG_ABS"
echo "  gRPC    : localhost:$GRPC_PORT"
echo "  HTTP    : localhost:$HTTP_PORT"
if [[ -n "$TRACES_FILE_ABS" ]]; then
  echo "  Traces  : $TRACES_FILE_ABS"
  echo "  Logs    : $LOGS_FILE_ABS"
  echo "  Metrics : $METRICS_FILE_ABS"
fi
echo ""

FILE_MOUNT_ARGS=()
if [[ -n "$TRACES_FILE_ABS" ]]; then
  FILE_MOUNT_ARGS=(
    -v "${TRACES_FILE_ABS}:/tmp/otel-traces.ndjson"
    -v "${LOGS_FILE_ABS}:/tmp/otel-logs.ndjson"
    -v "${METRICS_FILE_ABS}:/tmp/otel-metrics.ndjson"
  )
fi

docker run \
  --name "$CONTAINER_NAME" \
  --rm \
  -p "${GRPC_PORT}:4317" \
  -p "${HTTP_PORT}:4318" \
  -v "${CONFIG_ABS}:/etc/otelcol/config.yaml:ro" \
  "${FILE_MOUNT_ARGS[@]+"${FILE_MOUNT_ARGS[@]}"}" \
  "$COLLECTOR_IMAGE" \
  --config /etc/otelcol/config.yaml
