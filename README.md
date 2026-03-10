# Honeycomb Agent Skill

Honeycomb observability skills for AI coding agents. Adds query patterns, production investigation workflows, SLOs & triggers, OpenTelemetry instrumentation, and Beeline migration guidance. Designed to complement the [Honeycomb MCP server](https://docs.honeycomb.io/integrations/mcp/).

## What's included

- **8 skills** — observability fundamentals, query patterns, production investigation, SLOs & triggers, OpenTelemetry instrumentation, OpenTelemetry migration, Beeline migration, board creation
- **2 agents** — `honeycomb-investigator` for autonomous multi-step production debugging, `instrumentation-advisor` for codebase-to-Honeycomb gap analysis (Claude Code only)
- **1 command** — `/honeycomb-setup` for interactive MCP server configuration (Claude Code only)

## Supported Tools

**Full Plugin Install:**
| Tool | Install |
|------|---------|
| Claude Code | `claude plugin marketplace add honeycombio/agent-skill` then `claude plugin install honeycomb` |
| Cursor | Settings > Rules > Add Remote Rule > `https://github.com/honeycombio/agent-skill` |
| Augment (Auggie CLI) | `auggie plugin marketplace add honeycombio/agent-skill` then `auggie plugin install honeycomb` |
| GitHub Copilot CLI | `copilot plugin install honeycombio/agent-skill:honeycomb` |

**Skills + MCP (manual setup):**
| Tool | Skills Directory | MCP Config |
|------|-----------------|------------|
| VS Code Copilot | `.github/skills/` | `.vscode/mcp.json` |
| OpenAI Codex CLI | `.agents/skills/` | `~/.codex/config.toml` |
| Cline | Rules system | `cline_mcp_settings.json` |

**MCP Server Only:**
Windsurf, Amazon Q Developer, Continue, and Copilot Coding Agent can connect the Honeycomb MCP server directly. See [Honeycomb Docs: MCP Configuration](https://docs.honeycomb.io/integrations/mcp/configuration-guide/) for setup instructions.

For detailed setup instructions for each tool, see [Honeycomb Docs: Agent Skills Setup](https://docs.honeycomb.io/integrations/agent-skills/).

## Install

### Claude Code

#### Marketplace (preferred)

```bash
claude plugin marketplace add honeycombio/agent-skill
claude plugin install honeycomb
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

### Augment (Auggie CLI)

```bash
auggie plugin marketplace add honeycombio/agent-skill
auggie plugin install honeycomb
```

### GitHub Copilot CLI

```bash
copilot plugin install honeycombio/agent-skill:honeycomb
```

## Tests

```bash
python -m venv .venv && source .venv/bin/activate
make install
make test
```

Structural tests validate plugin layout, frontmatter, and hook behavior — no API keys needed.

## Versioning

This plugin uses semantic versioning. Tags follow the format `v{major}.{minor}.{patch}`.
Marketplace users can pin to a specific version via git ref.
