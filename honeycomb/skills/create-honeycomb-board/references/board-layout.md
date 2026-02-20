# Board Layout Reference

## The panels array

`create_board` takes a single `panels` array. Each panel must have a `type` field:

| type | Required fields | Optional fields |
|------|----------------|-----------------|
| `"query"` | `type`, `id` (query run PK like `QR-abc123`) | `name`, `description`, `chart_type`, `display_style`, `size` |
| `"slo"` | `type`, `id` (SLO PK) | `size` |
| `"text"` | `type`, `content` (Markdown, max 10000 chars) | `size` |

Panels appear on the board in the order listed. Order matters — put the most important context first.

## Grid system

The board uses a **12-column grid**. Panels wrap to the next row when total width exceeds 12.

Use `size: { "width": N, "height": N }` to control each panel:
- `width`: 1–12 columns (default fills available space)
- `height`: rows (default varies by panel type)

### Layout examples

**Stat row** — three stats side-by-side at the top:
```json
{ "type": "query", "id": "QR-...", "name": "Request Rate", "chart_type": "stat", "size": { "width": 4 } },
{ "type": "query", "id": "QR-...", "name": "Error Rate",   "chart_type": "stat", "size": { "width": 4 } },
{ "type": "query", "id": "QR-...", "name": "P95 Latency",  "chart_type": "stat", "size": { "width": 4 } }
```

**Full-width heatmap**:
```json
{ "type": "query", "id": "QR-...", "name": "Latency Distribution", "size": { "width": 12, "height": 3 } }
```

**Two graphs side-by-side**:
```json
{ "type": "query", "id": "QR-...", "name": "Request Rate", "size": { "width": 6 } },
{ "type": "query", "id": "QR-...", "name": "Error Rate",   "size": { "width": 6 } }
```

**SLO widget beside a summary graph**:
```json
{ "type": "slo",   "id": "SLO-...",  "size": { "width": 4 } },
{ "type": "query", "id": "QR-...",   "size": { "width": 8 } }
```

There's no one right layout. Design it to tell a story — context at the top, most important signals next, breakdowns below.

## Chart types

| value | Description |
|-------|-------------|
| `"default"` | Honeycomb chooses (correct for heatmaps; use when unsure) |
| `"none"` | Table only |
| `"line"` | Line chart |
| `"stacked"` | Stacked area chart |
| `"bar"` | Bar timeseries |
| `"stat"` | Single value / stat panel |
| `"categorical_bar"` | Categorical bar chart |
| `"pie"` | Pie chart |

Guidance:
- `"default"` for heatmaps — do not override this
- `"stat"` for single-number highlights (error rate %, unique users, P95 value)
- `"line"` for time-series comparisons and trends
- `"pie"` or `"categorical_bar"` for categorized breakdowns
- When there's a GROUP BY, `"combo"` display style shows both graph and table

## Display styles

| value | Description |
|-------|-------------|
| `"chart"` | Visualization only (tool default) |
| `"table"` | Data table only |
| `"combo"` | Both chart and table |

Use `"combo"` when there's a GROUP BY / breakdown — you want to see both the graph and the ranked table. Use `"chart"` for clean time series. Stat panels (`chart_type: "stat"`) pair with `"chart"` display.

## Preset filters

`preset_filters` creates interactive dropdown controls on the board — viewers can filter all graphs by a column value without editing queries. Maximum 5.

```json
"preset_filters": [
  { "column": "http.route",       "alias": "Route" },
  { "column": "app.region",       "alias": "Region" },
  { "column": "app.account_tier", "alias": "Account Tier" }
]
```

Good candidates: route, region, account tier, deployment version, user type. Especially useful for boards shared across teams or used during incidents. If the service has meaningful segmentation columns, suggest preset filters.

## Tags

```json
"tags": ["team:platform", "tier:critical"]
```

Use `list_boards` to see existing tags and follow those formats.

**Format rules:**
- **Keys**: lowercase letters only, max 32 chars, no hyphens
- **Values**: start with lowercase, can contain letters/numbers/`-`/`/`, max 128 chars
- ❌ WRONG: `"user-facing:true"` (hyphen in key)
- ✅ RIGHT: `"userfacing:true"`, `"tier:critical"`

## Duplicate query trick

Honeycomb rejects duplicate queries on a board. To show the same data in two formats (e.g., stat + line), add a trivially-true filter to one of them — for example `service.name exists`. Results are identical but the queries are technically different.

Keep the timeframe consistent between both panels so the numbers agree.
