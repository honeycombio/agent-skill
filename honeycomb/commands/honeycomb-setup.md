---
name: honeycomb-setup
description: Set up the Honeycomb MCP server connection for Claude Code
---

# Honeycomb MCP Setup

Guide the user through connecting Claude Code to Honeycomb's MCP server. Use `AskUserQuestion`
to walk through the setup interactively.

## Step 1: Prerequisites

Ask the user:
1. Do they have a Honeycomb account?
2. Is Honeycomb Intelligence enabled on their team? (Required for MCP)

If they're unsure about Honeycomb Intelligence, it's an add-on feature that enables AI-powered
tools. They can check with their Honeycomb team admin.

## Step 2: Choose Region

Use `AskUserQuestion` to ask: "Which Honeycomb region are you using?"
- **US** (default): `https://mcp.honeycomb.io/mcp`
- **EU**: `https://mcp.eu1.honeycomb.io/mcp`

## Step 3: Choose Authentication Method

Use `AskUserQuestion` to ask: "How would you like to authenticate?"

### Option A: OAuth (Recommended)

Run the following command based on their region:

**US:**
```bash
claude mcp add honeycomb --transport http https://mcp.honeycomb.io/mcp
```

**EU:**
```bash
claude mcp add honeycomb --transport http https://mcp.eu1.honeycomb.io/mcp
```

After adding, the user will be prompted to authenticate in their browser on first use.

### Option B: API Key (Headless/Unattended Only)

For headless environments where OAuth is not available, use `AskUserQuestion` to collect:
1. Their API key (format: `<Key ID>:<Secret Key>`)
2. Their region (from Step 2)

Then run the appropriate command:

**US:**
```bash
claude mcp add honeycomb --transport http https://mcp.honeycomb.io/mcp --header "Authorization: Bearer <KEY_ID>:<SECRET_KEY>"
```

**EU:**
```bash
claude mcp add honeycomb --transport http https://mcp.eu1.honeycomb.io/mcp --header "Authorization: Bearer <KEY_ID>:<SECRET_KEY>"
```

Replace `<KEY_ID>:<SECRET_KEY>` with the user's actual API key.

**API Key requirements:**
- Must be a Management API Key (not Ingest key)
- Must have "Model Context Protocol" scope (read)
- Must have "Environments" scope (read)
- For `create_board`: also need "Model Context Protocol" scope (write)
- Format: `<Key ID>:<Secret Key>` (with colon separator)

## Step 4: Verify Connection

Use `AskUserQuestion` to ask: "Would you like me to verify the connection now?"

If yes:
1. Run `/mcp` to confirm the Honeycomb server appears
2. Call `get_workspace_context` to verify data access
3. Show the user their available environments and datasets

## Step 5: Context Priming (Recommended)

Use `AskUserQuestion` to ask: "Would you like me to add Honeycomb context priming to your CLAUDE.md?"

If yes, add this to their project's `CLAUDE.md`:

```markdown
## Honeycomb MCP Usage

When working with Honeycomb:
- Always call `get_workspace_context` first to understand available environments and datasets
- Use `find_columns` or `get_dataset_columns` to discover fields before running queries
- Use human-readable time ranges (e.g., "last 2 hours", "24h") — avoid epoch timestamps
- Specify the environment and dataset explicitly in every query
```

## Troubleshooting

- **OAuth errors**: Report to Honeycomb support or Pollinators Slack
- **API key format error**: Ensure format is `<Key ID>:<Secret Key>` with colon
- **No tools found**: Verify Honeycomb Intelligence is enabled for your team
- **Session timeout**: MCP sessions may time out after 24 hours — re-authenticate
- **"list_environments" or similar errors**: The MCP server uses `get_workspace_context` and `get_environment`, not `list_environments`
