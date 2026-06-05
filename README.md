# Honeycomb Agent Skill

Honeycomb observability skills for AI coding agents. Adds query patterns, production investigation workflows, SLOs & triggers, OpenTelemetry instrumentation, and Beeline migration guidance. Designed to complement the [Honeycomb MCP server](https://docs.honeycomb.io/integrations/mcp/).

## What's included

- **8 skills** — observability fundamentals, query patterns, production investigation, SLOs & triggers, OpenTelemetry instrumentation, OpenTelemetry migration, Beeline migration, board creation
- **2 agents** — `honeycomb-investigator` for autonomous multi-step production debugging, `instrumentation-advisor` for codebase-to-Honeycomb gap analysis (Claude Code and Cursor)
- **1 command** — `/honeycomb-setup` for interactive MCP server configuration (Claude Code and Cursor)

## Supported Tools

**Full Plugin Install:**
| Tool | Install |
|------|---------|
| Claude Code | `claude plugin marketplace add honeycombio/agent-skill` then `claude plugin install honeycomb` |
| OpenAI Codex | `codex plugin marketplace add honeycombio/agent-skill` then install Honeycomb from the plugin directory |
| Cursor | Team Marketplace import, or local plugin install — [see Cursor setup](#cursor) |
| Augment (Auggie CLI) | `auggie plugin marketplace add honeycombio/agent-skill` then `auggie plugin install honeycomb` |
| GitHub Copilot CLI | `copilot plugin install honeycombio/agent-skill:honeycomb` |

**Skills + MCP (manual setup):**
| Tool | Skills Directory | MCP Config |
|------|-----------------|------------|
| VS Code Copilot | `.github/skills/` | `.vscode/mcp.json` |
| OpenAI Codex CLI | `honeycomb/skills/` | `~/.codex/config.toml` |
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

Honeycomb ships as a Cursor **plugin** (skills, agents, the `/honeycomb-setup`
command, hooks, and the MCP server). It is **not** a project rule, so the
**Rules > Add Remote Rule** flow does not work — that importer only accepts
`.mdc` rule files, and this repo intentionally ships none. Use a plugin install
path instead.

#### Teams / Enterprise — Marketplace import

1. Open the Cursor dashboard → **Settings > Plugins**.
2. Under **Team Marketplaces**, import from the repository URL:
   `https://github.com/honeycombio/agent-skill`
3. Add the `honeycomb` plugin to your marketplace and grant team access.

#### Individual users — local install

Cursor has no one-click GitHub import for individual plugins, so install the
plugin into Cursor's local plugins folder:

```bash
git clone https://github.com/honeycombio/agent-skill.git
mkdir -p ~/.cursor/plugins/local
ln -s "$(pwd)/agent-skill/honeycomb" ~/.cursor/plugins/local/honeycomb
```

Then restart Cursor, or run **Developer: Reload Window** from the command
palette. The `honeycomb/` directory is a self-contained plugin (its
`.cursor-plugin/plugin.json` declares the skills, agents, command, hooks, and
MCP server). To update later: `cd agent-skill && git pull`.

Once loaded, type `/` in Agent chat and search for a skill name to invoke it
manually. See [Cursor: Plugins](https://cursor.com/docs/plugins) and
[`honeycomb/.cursor-plugin/INSTALL.md`](honeycomb/.cursor-plugin/INSTALL.md) for
more detail.

### OpenAI Codex

```bash
codex plugin marketplace add honeycombio/agent-skill
```

After adding the marketplace, restart Codex, open the plugin directory, select **Honeycomb Plugins**, and install Honeycomb.

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
