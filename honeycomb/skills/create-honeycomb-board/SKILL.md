---
name: create-honeycomb-board
description: >
  Design and then create a board (dashboard) in Honeycomb with queries and SLOs.
  Use when asked to "create a board", "make a board", "build a dashboard",
  "create a Honeycomb board", "make a dashboard in Honeycomb",
  "set up a board", or any request to design and create or build a Honeycomb board or dashboard.
allowed_tools:
  - mcp__honeycomb__create_board
  - mcp__honeycomb__run_query
  - mcp__honeycomb__get_query_results
  - mcp__honeycomb__get_workspace_context
  - mcp__honeycomb__get_environment
  - mcp__honeycomb__get_dataset
  - mcp__honeycomb__get_dataset_columns
  - mcp__honeycomb__find_columns
  - mcp__honeycomb__find_queries
  - mcp__honeycomb__get_slos
  - mcp__honeycomb__get_triggers
  - mcp__honeycomb__list_boards
  - Read
  - Grep
  - Glob
  - AskUserQuestion
---

# Create a Honeycomb Board

Build a board (dashboard) in Honeycomb using the `create_board` MCP tool.
There is no update tool — define it well before creating.

When building a board, think about the purpose and time frame involved. Some examples:

- a board for a service. This should be timeless, looking at the service's health, performance, and business metrics. Do not do any problem diagnosis or investigation when building this board. Do not express opinions or summarize graphs in text panels. The board should be a representation of the service's health at whatever moment someone looks at it.
- a board for a feature. This should look at the feature's usage trends, and its impact on the business. This board would have a time frame of 7 days, and would not include any infrastructure metrics or service dependencies.
- a board for a problem. This might be created during an incident, or afterward. This one would have a time frame specific to the incident. It would include investigations, and your opinions about what is happening. Patterns of what to look for are appropriate here.

## Workflow

### Gather SLOs

Use `get_slos` to list SLOs in the environment. Relevant SLOs will go on the board as `slo` panels.

### Gather descriptive context

Look at the code and docs (using Read/Grep/Glob) to understand the service or feature. Use this to write a text panel. Link to GitHub or documentation if you can.

This will vary greatly depending on the purpose of the board.

Description of the application and link to the code - great for a service board.

What is the feature, and what business impact does it have? - great for a feature board.

What is the problem, and what is the impact? What patterns do we see? - great for a problem board.

### Build candidate queries

**Get Honeycomb context**: Call `get_workspace_context` for available environments. Use `get_environment` to find datasets — each dataset corresponds to an `OTEL_SERVICE_NAME`.

**Code context**: Look at the language and any custom attributes (often prefixed `app.`). Custom fields are prime candidates for breakdowns and business metrics.

**Discover columns**: Use `find_columns` or `get_dataset_columns`. Pay special attention to non-standard columns — those are specific to the application.

**Find queries**: Use `find_queries` to see what people have already queried. Check `get_triggers` for what they alert on — those indicate what matters.

**Time range**: Default to 2 hours. Use 8–24 hours for lower-volume services. Use 7 days for feature usage boards. Keep it consistent across all panels.

Aim for 6–12 graphs. Stat panels are bonus — they don't count against this limit.

List your candidate queries for the user with reasons before running them. See [board-queries.md](references/board-queries.md) for what to include and how to write each kind.

### Run and check queries

Use `run_query` for each candidate query. Each result returns a query run PK (like `QR-abc123`) — you'll use this as the panel `id` when building the board.

Fix errors. Eliminate queries that return no interesting results.

### Plan the layout

Think about visual flow and how to make the board expressive. The board uses a 12-column grid — stat panels can sit side-by-side, a heatmap deserves full width, breakdowns benefit from extra height. See [board-layout.md](references/board-layout.md) for sizing examples.

Consider `preset_filters` if viewers will want to slice the board interactively (by route, region, account tier, etc.).

### Show the proposed board to the user — always, without exception

Display:

- The text panel content
- SLOs to include
- Each query: name, description, chart type, display style, example results
- Planned layout (sizing and groupings)
- Tags
- Any preset filters

End with: "Here's the board I'd create. Shall I go ahead?"

**This step is non-negotiable.** If the user says "just create it", "I trust you", or "skip the preview" — show the plan anyway. The user cannot meaningfully confirm something they haven't seen. There is no way to update a board after creation; the only fix is to delete it and start over. Showing the plan first protects them even when they think they don't need it.

The one exception: if the user has already reviewed and approved a specific plan in this conversation, you may proceed.

### Create the board

Call `create_board` with a `panels` array. Every panel requires a `type` field — `"query"`, `"slo"`, or `"text"` — that determines what other fields apply. See [board-layout.md](references/board-layout.md) for the full field reference.

```json
{
  "environment_slug": "production",
  "name": "Checkout Service",
  "description": "...",
  "panels": [
    {
      "type": "text",
      "content": "## Checkout Service\nOwned by Platform team. [Source](https://github.com/...)"
    },
    {
      "type": "slo",
      "id": "SLO-abc123",
      "size": { "width": 4 }
    },
    {
      "type": "query",
      "id": "QR-abc123",
      "name": "Request Rate",
      "chart_type": "stat",
      "display_style": "chart",
      "size": { "width": 4 }
    },
    {
      "type": "query",
      "id": "QR-def456",
      "name": "Error Rate",
      "chart_type": "stat",
      "display_style": "chart",
      "size": { "width": 4 }
    },
    {
      "type": "query",
      "id": "QR-ghi789",
      "name": "Latency Distribution",
      "description": "Overall request latency as a heatmap",
      "chart_type": "default",
      "display_style": "chart",
      "size": { "width": 12, "height": 3 }
    }
  ],
  "preset_filters": [{ "column": "http.route", "alias": "Route" }],
  "tags": ["team:platform", "tier:critical"]
}
```

If there are plenty of root spans, then you can use this as a way to count requests.

For downstream services, the right query (in OpenTelemetry) is:

```javascript
filters: [{ column: "span.kind", op: "=", value: "server" }];
```

**Graph latency as a heatmap**:
For overall latency, use the same filter clause as for counting requests, since it's the top-level service latency that we're interested in.
Graph HEATMAP(duration_ms), because this is the most useful. you might also include P95(duration_ms) or similar as a stat panel.

When there's a breakdown in the query, heatmap is not ideal. In that case, graph P95 instead.

**Find queries**: Use `find_queries` to list the queries in the environment and interesting datasets. See what people query in this environment. This can give you ideas for what to include on the board.

**Check triggers**:
Use `get_triggers` to list the triggers in the environment. If there are relevant triggers, they indicate things that people care about. You can put their queries on the board.

**Query service dependencies**: When making a board for a service, it can be interesting to graph the performance of its dependencies.

To find dependencies, run an environment-wide query:
WHERE parent.span.kind = client AND parent.service.name = service-of-interest GROUP BY service.name
Then those service.names will belong to dependencies of the service-of-interest.

**Calculate error rate**:
To graph error rate, you'll need a calculated field. Include a calculated field in the query, using whatever status field indicates error in this data.

```javascript
calculated_field: error_pct = MUL(IF($error, 1, 0), 100);
calculation: AVG(error_pct);
// Result: 4.94 means 4.94% error rate
```

Include this as two queries: a stat panel, and a line graph.

You might also count errors by exception.message, if there's interesting stuff there.

**Look for Metrics**: If the 'Metrics' dataset exists, then we can might find infrastructure metrics. The trick is to find the right ones.
Query the values of resource attributes in the traces, such as k9s.deployment.name or host.name, that might indicate the infrastructure layer where this particular service runs.
Then look for the same attribute in the Metrics dataset. See if you can get examples of the metrics available. This can take some investigation, to find the right filters and metric names.

**Categorize useful fields**:

If there are custom fields that represent categories, like account type or free vs paid users, these are useful graphs. Is service better or worse for paid accounts? How much of the app's work is serving free users?

Some custom fields can become categories with a classification function. After you look at some values, you can make categories of fields that are useful to graph. Then you can make a pie chart with them. For instance:

```javascript
// Error classification by status code
error_type = IF(
  GTE($http.status_code, 500),
  "5xx_server_error",
  IF(GTE($http.status_code, 400), "4xx_client_error", "success"),
);

// High-value transaction flag
is_high_value = GTE($app.cart_total, 1000);

// Slow request indicator
is_slow = GT($duration_ms, 1000);

// Route categorization
route_category = IF(
  CONTAINS($http.route, "/product/"),
  "product_page",
  IF(CONTAINS($http.route, "/cart"), "cart_flow", "other"),
);
```

### List candidate queries

Include RED metrics, infrastructure metrics (CPU/memory/network) if available, and any custom metrics that seem important.

For instance, a board for a web service should count requests by endpoint. If user ID is a field, count requests by the top 10 users. Also COUNT_DISTINCT(user_id) or COUNT_DISTINCT(session_id) is a great stat panel.

You probably want 6-12 graphs. Stat panels are bonus, they don't count against the 6-12.

List these out for the user, along with your reasons for including them, while you work on checking each one.

### Check the queries

**Run queries**: Use `run_query` to execute each query. Each query result gives back a query run PK (like `QR-abc123`) that you'll need for the board.

**Check results**: Are the results interesting? Fix any errors, change or eliminate any empty queries.

### Format queries

- When a chart has a GROUP BY / breakdown, use `display_style: "combo"` so both the graph and table are visible.
- Most of the time, use `display_style: "combo"` to show both the graph and the overall number. Exceptions include: when there's a stat panel to give a big number.
- Give each query a descriptive `name` so the board is easy to read.
- In the description, put why the query seems interesting, and what it shows.

#### Chart Types

- default — Auto-select chart type (use for heatmaps)
- none — Table-only display
- line — Line chart (normal)
- stacked — Stacked area chart
- bar — Bar timeseries
- stat — Single value display (stat panel)
- categorical_bar — Categorical bar chart
- pie — Pie chart

#### Secret trick

If you want to display the same data in two different formats, you need to get past Honeycomb's "no duplicate queries on a board" restriction. This is easy enough: add 'service.name exists' to the filter on one of the queries. Something that's true for every event, so that the results are the same, but the query is technically different.

Be sure to keep the timeframe consistent, because we want the data to say the same thing in both places.

#### Display Styles

- `chart` - Visualization only (clean for time series)
- `table` - Data table only (for debugging)
- `combo` - Both chart and table (best for breakdowns)

### Choose metatdata for the board

The name should be short, like "Checkout Service Performance". The description should be a paragraph that describes the board, and what it's for.

For tags, use `list_boards` to see what tags exist, and follow those formats.

#### Tag Format (Strict!)

- **Keys**: lowercase letters only, max 32 chars (no hyphens!)
- **Values**: start with lowercase, can have letters/numbers/-//, max 128 chars
- Format: `["key:value", "team:platform", "tier:critical"]`
- ❌ WRONG: `"user-facing:true"` (hyphen in key)
- ✅ RIGHT: `"tier:critical"` or `"userfacing:true"`

### Lay out the board

Panels appear in the order you specify them in the `panels` array. The board uses a **12-column grid** that wraps. Each panel has an optional `size` with `width` (1-12 columns) and `height` (rows).

Follow this recommended layout from top to bottom:

#### Row 1: Introduction — text panel + primary SLO

Place a text panel (width 8). If there is a primary SLO, place it alongside (width 4). The text panel should describe the board's purpose, link to relevant code or docs, and note what to watch for.

```
┌──── text (8) ─────┬── SLO (4) ──┐
```

#### Row 2: Other SLOs at 1/3 width

If there are additional relevant SLOs, place them in a row at width 4 each (up to 3 across).

```
├── SLO (4) ──┬── SLO (4) ──┬── SLO (4) ──┤
```

#### Row 3: Stat panels at 1/4 width

Key single-number metrics (P95 latency, error rate %, request count, unique users) work well as `chart_type: "stat"` at width 3, fitting 4 across.

```
├─ stat (3) ─┬─ stat (3) ─┬─ stat (3) ─┬─ stat (3) ─┤
```

#### Remaining rows: Queries with explanatory text

For the main query panels, use width 6 (two across) or width 12 (full width).

For particularly interesting or non-obvious queries, add a narrow text panel (width 3-4) next to the query (width 8-9) on the same row. Use the text panel to explain what to look for, what normal looks like, or what actions to take if values change.

```
├── text (3) ──┬──── query (9) ────────────┤
├──── query (6) ─────┬──── query (6) ──────┤
```

Not every query needs an explanatory text panel — just the ones where the meaning isn't obvious from the name alone, or where there's useful context about thresholds or expected behavior.

#### Layout tips

- Keep heights consistent within a row for visual alignment
- SLO panels work well at height 4
- Stat panels work well at height 4
- Simple chart-only query panels work at height 4
- Query panels with two graphs and `display_style: "chart"` need height 7
- For queries with `display_style: "combo"`, if they have no breakdowns, add 1 to height.
- For queries with `display_style: "combo"` and a breakdown, add at 3-5 height units, depending on how many rows the table needs.
- Text panels for row headers work at height 1; explanatory text panels next to queries should match the query panel height
- Heatmap panels work at height 5

### Display the proposed board format to the user.

For each panel, display:

- **Text panels**: Show the **full markdown content** that will appear on the board. The user needs to review the exact wording before creation since boards can't be updated.
- **SLO panels**: Show the SLO name, target, and current compliance.
- **Query panels**: Show the name, description, chart type, display style, and a **link to the query** (the `query_url` from the run_query result metadata). Briefly describe what the results showed.
- **Tags**: Display the tags you plan to add to the board.

Ask the user what changes they would like.

### Get confirmation from the user.

Don't create it without confirmation! If the user wants changes from you after creation, they'll have to delete the board manually. You can only create a new version.

### Finally, create the board.

Call `create_board` with:

- `environment_slug` (required)
- `name` (required)
- `description` (recommended)
- `panels` array — all panels (queries, SLOs, and text) in a single ordered array. Each panel has:
  - `type`: `"query"`, `"slo"`, or `"text"`
  - `id`: query run PK (for query panels) or SLO ID (for slo panels)
  - `content`: markdown text (for text panels)
  - `name`, `description`: display label and explanation (for query panels)
  - `chart_type`: `"default"`, `"line"`, `"stacked"`, `"bar"`, `"stat"`, `"categorical_bar"`, `"pie"`, `"none"`
  - `display_style`: `"chart"`, `"table"`, or `"combo"`
  - `size`: `{ width: 1-12, height: N }` — grid wraps at 12 columns
- `tags` array for organization (format: `key:value`)
- `preset_filters` array for filter dropdowns (max 5)

### Follow up

Link the user to the board.
