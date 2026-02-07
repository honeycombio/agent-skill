# Honeycomb Claude Code Plugin

A [Claude Code plugin](https://docs.anthropic.com/en/docs/claude-code/plugins) that adds Honeycomb observability skills, an investigation agent, and a setup command. Designed to complement the [Honeycomb MCP server](https://docs.honeycomb.io/integrations/mcp/).

## What's included

- **5 skills** — query patterns, production investigation, SLOs & triggers, OpenTelemetry instrumentation, Beeline migration
- **1 agent** — `honeycomb-investigator` for autonomous multi-step production debugging
- **1 command** — `/honeycomb-setup` for interactive MCP server configuration

## Install

```bash
claude plugin add ./honeycomb
```

Requires the Honeycomb MCP server to be configured (the `/honeycomb-setup` command can help).

## Tests

```bash
python -m venv .venv && source .venv/bin/activate
make install
make test
```

Structural tests validate plugin layout, frontmatter, JSON query examples against schema, MCP tool references, and content quality — no API keys needed.
