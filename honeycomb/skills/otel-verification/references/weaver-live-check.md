# Checking emitted attributes against a registry with weaver

When a weaver registry was provided *and weaver checks are on*, use weaver to compare the attributes
the service **actually emits** against the registry rather than eyeballing it. There are two ways to
feed weaver, keyed by how you sourced the telemetry (step 1 of the skill):

- **You ran the app** → judge the **live stream** through a collector into `weaver registry
  live-check`'s OTLP receiver, as traffic flows. Needs `weaver` **and** an OTel collector installed.
  See *Live stream via a collector* below.
- **You are judging telemetry already in Honeycomb** → build a **JSON sample** of the emitted
  attributes and check it offline. Needs `weaver` only — no live traffic, no OTLP receiver, no app
  boot. See *Build the sample file from Honeycomb* below.

Either way you read the same verdict fields (see *Read the verdict from `statistics`*) and split the
result into `weaver_custom_attrs` / `weaver_missing_attrs` the same way.

## Live stream via a collector (when you ran the app)

Start `weaver registry live-check` in streaming mode — it stands up an OTLP receiver and an admin
endpoint that serves the report:

```
weaver registry live-check --registry <registry-dir> --format json
```

Point the app's OTLP export at a **minimal local collector** that fans every signal out to **both**
Honeycomb (so you can also run the query-based checks) and weaver's live-check receiver. A minimal
`otelcol-contrib` config:

```yaml
receivers:
  otlp:
    protocols: { grpc: {}, http: {} }
exporters:
  otlphttp/honeycomb:                     # so the data is queryable in Honeycomb too
    endpoint: ${OTEL_EXPORTER_OTLP_ENDPOINT}
    headers: { x-honeycomb-team: ${HONEYCOMB_INGEST_KEY} }
  otlp/weaver:
    endpoint: <weaver-live-check-otlp-host:port>
    tls: { insecure: true }
service:
  pipelines:
    traces:  { receivers: [otlp], exporters: [otlphttp/honeycomb, otlp/weaver] }
    metrics: { receivers: [otlp], exporters: [otlphttp/honeycomb, otlp/weaver] }
    logs:    { receivers: [otlp], exporters: [otlphttp/honeycomb, otlp/weaver] }
```

Drive traffic (skill step 1), let it flush, then read the report from weaver's admin endpoint (or the
report it writes on shutdown) and pull `.statistics` — the same object described below. The advantage
over the sample-file path is that weaver sees the **real values and types** as emitted, not
placeholders.

## Build the sample file from Honeycomb

Get the emitted attributes from Honeycomb (`get_dataset_columns` / `find_columns` across the trace,
metric, and log datasets that recently received data). The sample file is a JSON array where each
element is a **tagged sample**; for attribute coverage you only need `attribute` samples (`span` /
`metric` / `log` are also accepted). Emit one entry per column name — the `value` can be a real
observed value (from `get_span_details` top values) or any placeholder of the right type; only the
`name` is matched:

```json
[
  { "attribute": { "name": "http.route",  "value": "/api/articles/:slug" } },
  { "attribute": { "name": "app.user.id", "value": "u_123" } }
]
```

Drop Honeycomb's built-in/meta columns (`Timestamp`, `trace.trace_id`, `trace.span_id`,
`duration_ms`, `name`, `service.name`, …) — they aren't semantic-convention attributes and just add
noise.

## Run the check (sample-file path)

It exits without needing a live stream:

```
weaver registry live-check --registry <registry-dir> --input-source emitted.json --input-format json --no-stream --format json
```

**Run it once and read `.statistics` — don't re-run live-check with a succession of ad-hoc greps to
reverse-engineer the output shape.** The whole verdict is in one object; pull it in a single pass:

```
weaver registry live-check --registry <registry-dir> --input-source emitted.json --input-format json --no-stream --format json \
  | jq '.statistics'          # or, if jq is absent:
  # python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin)["statistics"], indent=2))'
```

Do **not** pass `--include-unreferenced`: it folds the entire upstream semconv into "the registry"
(hundreds of attributes), which flattens `registry_coverage` and buries the "defined but never
emitted" signal under attributes the app never touches. Leaving it off keeps the registry universe
to what the app actually authored — standard attributes it emits surface under
`seen_non_registry_attributes`, where you check each against `search_semconv` /
`get_semconv_attribute` and credit only the ones that match a **current** convention. Flag the rest
as findings — both the genuinely-unknown names **and** any that match a convention the spec has since
deprecated or renamed to a newer spelling. Matching a real convention is not enough on its own; a
deprecated match is still a finding to report.

## Read the verdict from `statistics`

- `seen_non_registry_attributes` — emitted but **absent from the registry** (undocumented; the
  registry is an incomplete manifest). Ignore standard attributes the registry deliberately leaves
  to imports if that's the org's convention; the rest are findings.
- `seen_registry_attributes` with a **count of 0** — defined in the registry but **never emitted**
  (stale, misnamed, or a pipeline that was never wired).
- `registry_coverage` — the fraction of the registry actually observed.

The registry is the standard here; a mismatch either way is a finding. This is the check that the
registry is a truthful manifest of what the app emits.
