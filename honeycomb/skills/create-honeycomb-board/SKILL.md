---
name: create-honeycomb-board
description: >
  Design and then create a board (dashboard) in Honeycomb with queries and SLOs.
  Trigger phrases: "create a board", "make a board", "build a dashboard",
  "create a Honeycomb board", "make a dashboard in Honeycomb",
  "set up a board", "dashboard for my service", "visualize service health",
  "golden signals dashboard", "set up monitoring board",
  or any request to design and create or build a Honeycomb board or dashboard.
metadata:
  version: "1.0.0"
allowed-tools:
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

List your candidate queries for the user with reasons before running them. See `${CLAUDE_PLUGIN_ROOT}/skills/create-honeycomb-board/references/board-queries.md` for what to include and how to write each kind.

### Run and check queries

Use `run_query` for each candidate query. Each result returns a query run PK (like `QR-abc123`) — you'll use this as the panel `id` when building the board.

Fix errors. Eliminate queries that return no interesting results.

### Plan the layout

Think about visual flow and how to make the board expressive. The board uses a 12-column grid — stat panels can sit side-by-side, a heatmap deserves full width, breakdowns benefit from extra height. See `${CLAUDE_PLUGIN_ROOT}/skills/create-honeycomb-board/references/board-layout.md` for sizing examples.

Consider `preset_filters` if viewers will want to slice the board interactively (by route, region, account tier, etc.).

### Show the proposed board to the user — always, without exception

For each panel, display:

- **Text panels**: Show the **full markdown content** that will appear on the board. The user needs to review the exact wording before creation since boards can't be updated.
- **SLO panels**: Show the SLO name, target, and current compliance.
- **Query panels**: Show the name, description, chart type, display style, and a **link to the query** (the `query_url` from the run_query result metadata). Briefly describe what the results showed.
- Planned layout (sizing and groupings)
- **Tags**: Display the tags you plan to add to the board.
- Any preset filters

End with: "Here's the board I'd create. Shall I go ahead?"

**This step is non-negotiable.** If the user says "just create it", "I trust you", or "skip the preview" — show the plan anyway. The user cannot meaningfully confirm something they haven't seen. There is no way to update a board after creation; the only fix is to delete it and start over. Showing the plan first protects them even when they think they don't need it.

The one exception: if the user has already reviewed and approved a specific plan in this conversation, you may proceed.

### Create the board

Call `create_board` with a `panels` array. Every panel requires a `type` field — `"query"`, `"slo"`, or `"text"` — that determines what other fields apply. See `${CLAUDE_PLUGIN_ROOT}/skills/create-honeycomb-board/references/board-layout.md` for the full field reference.

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

### Follow up

Link the user to the board.

## Cross-References
- For query construction patterns and calculated fields: **query-patterns** skill
- For SLO interpretation and burn alert design: **slos-and-triggers** skill
