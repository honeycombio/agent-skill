# Honeycomb Agent Skill

Honeycomb observability skills for AI coding agents. Adds query patterns, production investigation workflows, SLOs & triggers, OpenTelemetry instrumentation, and Beeline migration guidance. Designed to complement the [Honeycomb MCP server](https://docs.honeycomb.io/integrations/mcp/).

## What's included

- **5 skills** — query patterns, production investigation, SLOs & triggers, OpenTelemetry instrumentation, Beeline migration
- **1 agent** — `honeycomb-investigator` for autonomous multi-step production debugging (Claude Code only)
- **1 command** — `/honeycomb-setup` for interactive MCP server configuration (Claude Code only)

## Install

### Claude Code

#### Marketplace (preferred)

```bash
claude plugin marketplace add honeycombio/agent-skill
claude plugin install honeycomb@honeycomb-plugins
```

#### Direct from GitHub

```bash
claude plugin add github:honeycombio/agent-skill/honeycomb
```

#### Local development

```bash
claude plugin add ./honeycomb
```

Requires the Honeycomb MCP server to be configured (the `/honeycomb-setup` command can help).

### Cursor

1. Open Cursor Settings (`Cmd+Shift+J` on Mac, `Ctrl+Shift+J` on Windows/Linux)
2. Navigate to **Rules > Project Rules**
3. Click **Add Rule** and select **Remote Rule (Github)**
4. Enter: `https://github.com/honeycombio/agent-skill`

Skills will be imported into your project and available in Agent chat. Type `/` and search for a skill name to invoke it manually.

See the [Cursor skills documentation](https://cursor.com/docs/context/skills) for more details.

## Tests

```bash
python -m venv .venv && source .venv/bin/activate
make install
make test
```

Structural tests validate plugin layout, frontmatter, JSON query examples against schema, MCP tool references, and content quality — no API keys needed.

## Versioning

This plugin uses semantic versioning. Tags follow the format `v{major}.{minor}.{patch}`.
Marketplace users can pin to a specific version via git ref.
