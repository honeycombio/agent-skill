---
name: create-honeycomb-board
description: >
  Create a board (dashboard) in Honeycomb with queries and SLOs.
  Use when asked to "create a board", "make a board", "build a dashboard",
  "create a Honeycomb board", "make a dashboard in Honeycomb",
  "set up a board", or any request to create or build a Honeycomb board or dashboard.
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
Note that there is no tool to update the board, so we'll need to be careful to define it well before creating it.

1. **Text Panel** - Service context, links, what to watch
1. **SLOs** - Health at a glance
1. **RED Metrics** - Rate, Errors, Duration
1. **Business Metrics** - Revenue, users, conversions
1. **Breakdown Views** - By route/operation/status
1. **Infrastructure Metrics** - CPU, memory, network
1. **Dependencies** - Downstream service health

## Workflow

### Gather SLOs

**Find SLOs**: Use `get_slos` to list the SLOs in the environment. If there are relevant SLOs, you'll add them to the board.

### Gather descriptive context

Look at the code and docs to learn more about the service or problem or feature that the user wants a board around. Use this to write a text panel describing the board. Link to the code in GitHub, if you can, or documentation.

### Gather candidate queries

#### Time frame

The default timeframe is 2 hours. If this is a board for a service, that's reasonable. So is 8 hours or 24 hours for a lower-volume service.

If the board is for a feature, where we're looking at usage trends, then 7 days is better.

#### When to Use Each Aggregation

- `COUNT` - Request volume, error counts
- `AVG` - Error rates, business averages
- `HEATMAP` - Overall latency distribution visualization
- `P50/P95/P99` - Latency SLIs (P95 most common) -- these make nice stat panels. When graphing, favor heatmap.
- `COUNT_DISTINCT` - Unique users, sessions, products
- `SUM` - Revenue, transaction totals (rarely used for latency)
- `MAX/MIN` - Finding extremes (less common)

**Get Honeycomb context**: Call `get_workspace_context` to learn the available environments. Use `get_environment` to find out what datasets available. A dataset corresponds to an OTEL_SERVICE_NAME.

**Code context**:
Consider which area of the code is covered. Look at the code to see what language it's in, as this can tell you what fields designate errors.

Look for any custom attributes added in the code, because those are useful to graph, especially as a breakdown. Some codebases use `app.` as a prefix for custom fields.

**Discover columns**: Use `find_columns` or `get_dataset_columns` to identify relevant columns. Look for the standard OpenTelemetry status columns. Look also for columns that aren't standard, because these are likely significant to the application.

**Business metrics are the best measurements**: If you find any custom fields related to revenue or engagement or other business goals, include those!
This is a good time for SUM. How much money is in play? How much money was involved in errors?

**Figure out how to count requests**: Top-level services and downstream services have different spans representing incoming requests.
Figure out which a service is before counting requests.

In the dataset of interest, look for root spans with these conditions:

```javascript
filters: [
  { column: "trace.parent_id", op: "does-not-exist" },
  { column: "meta.signal_type", op: "=", value: "trace" },
];
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

### Display the proposed board format to the user.

Display the text panel, the SLOs, and the queries with names, descriptions, and display style. Link to a sample of each query. Describe the results that you saw.

Display the tags you plan to add to the board.

Ask the user what changes they would like.

### Get confirmation from the user.

Don't create it without confirmation! If the user wants changes from you after creation, they'll have to delete the board manually. You can only create a new version.

### Finally, create the board.

Call `create_board` with:

- `environment_slug` (required)
- `name` (required)
- `description` (recommended)
- `queries` array, each with `id` (the query run PK) and optionally `name`, `chart_type`, and `display_style`
- `slo_ids` array if including SLOs
- `text_panels` array for markdown text panels
- `tags` array for organization (format: `key:value`)

### Follow up

Link the user to the board.
