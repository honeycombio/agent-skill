# Honeycomb Agent Skill

Honeycomb observability skills for AI coding agents. Adds query patterns, production investigation workflows, SLOs & triggers, OpenTelemetry instrumentation, and Beeline migration guidance. Designed to complement the [Honeycomb MCP server](https://docs.honeycomb.io/integrations/mcp/).

## What's included

- **9 skills** — observability fundamentals, query patterns, metrics queries, production investigation, SLOs & triggers, OpenTelemetry instrumentation, OpenTelemetry migration, Beeline migration, board creation
- **2 agents** — `honeycomb-investigator` for autonomous multi-step production debugging, `instrumentation-advisor` for codebase-to-Honeycomb gap analysis (Claude Code and Cursor)
- **1 command** — `/honeycomb-setup` for interactive MCP server configuration (Claude Code and Cursor)

## Supported Tools

**Full Plugin Install:**
| Tool | Install |
|------|---------|
| Claude Code | `claude plugin marketplace add honeycombio/agent-skill` then `claude plugin install honeycomb` |
| OpenAI Codex | `codex plugin marketplace add honeycombio/agent-skill` then install Honeycomb from the plugin directory |
| Cursor | [Install from cursor.directory](https://cursor.directory/plugins/honeycomb) — or Team Marketplace import ([setup](#cursor)) |
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

Honeycomb is a Cursor **plugin** (skills, agents, the `/honeycomb-setup`
command, hooks, and the MCP server). Install it from the Cursor plugin
directory:

**→ [cursor.directory/plugins/honeycomb](https://cursor.directory/plugins/honeycomb)**

Open the listing and use its **Install** action. The plugin's MCP server config
is shown for review before it's passed to Cursor — confirm it, then reload.

#### Distributing to a team

On Teams/Enterprise plans you can import this repo as a private **Team
Marketplace**: Cursor dashboard → **Settings > Plugins > Team Marketplaces >
Import**, then paste `https://github.com/honeycombio/agent-skill` and grant team
access. See [Cursor: Plugins](https://cursor.com/docs/plugins) for team
marketplace setup.

For a manual / local install (e.g. plugin development), see
[`honeycomb/.cursor-plugin/INSTALL.md`](honeycomb/.cursor-plugin/INSTALL.md).

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

The Claude Code plugin uses semantic versioning. Its version in
`honeycomb/.claude-plugin/plugin.json` is the single source of truth for update
detection. Every pull request that changes files under `honeycomb/` must bump
that version so existing installations receive the changes.

The repository-level marketplace version in `.claude-plugin/marketplace.json`
matches the plugin version. The marketplace plugin entry intentionally omits a
second version field because Claude Code gives the plugin manifest precedence.
