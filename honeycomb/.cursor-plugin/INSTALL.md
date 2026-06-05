# Installing the Honeycomb plugin in Cursor

Honeycomb ships as a Cursor **plugin** — skills, agents, the `/honeycomb-setup`
command, hooks, and the Honeycomb MCP server, all declared in
[`plugin.json`](./plugin.json).

## Recommended — Cursor plugin directory

Install from the public listing:
**[cursor.directory/plugins/honeycomb](https://cursor.directory/plugins/honeycomb)**

Open the listing and use its **Install** action. Cursor shows the plugin's MCP
server config for review before passing it to Cursor — confirm it, then restart
Cursor or run **Developer: Reload Window** from the command palette.

## Teams / Enterprise — Marketplace import

GitHub import is available on Teams and Enterprise plans via Team Marketplaces:

1. Open the Cursor dashboard → **Settings > Plugins**.
2. Under **Team Marketplaces**, import from the repository URL:
   `https://github.com/honeycombio/agent-skill`
3. Add the `honeycomb` plugin to your marketplace and grant team access.

## Manual / local install (development)

For plugin development or offline use, load it from Cursor's local plugins
folder by symlinking (recommended, so `git pull` keeps it current) or copying.

### macOS / Linux

```bash
git clone https://github.com/honeycombio/agent-skill.git
mkdir -p ~/.cursor/plugins/local
ln -s "$(pwd)/agent-skill/honeycomb" ~/.cursor/plugins/local/honeycomb
```

### Windows (PowerShell)

```powershell
git clone https://github.com/honeycombio/agent-skill.git
New-Item -ItemType Directory -Force "$env:USERPROFILE\.cursor\plugins\local" | Out-Null
New-Item -ItemType SymbolicLink `
  -Path "$env:USERPROFILE\.cursor\plugins\local\honeycomb" `
  -Target "$(Resolve-Path .\agent-skill\honeycomb)"
```

Then **restart Cursor**, or run **Developer: Reload Window** from the command
palette so Cursor rescans local plugins.

## Verify

The plugin root must contain `.cursor-plugin/plugin.json`:

```bash
ls ~/.cursor/plugins/local/honeycomb/.cursor-plugin/plugin.json
```

In Agent chat, type `/` and search for a skill name (e.g. `query-patterns`) to
confirm the skills loaded.

## Update

```bash
cd agent-skill && git pull
```

Reload the window afterward. (If you copied the directory instead of symlinking,
re-copy `honeycomb/` into `~/.cursor/plugins/local/`.)

## Uninstall

```bash
rm ~/.cursor/plugins/local/honeycomb   # removes the symlink, not your clone
```

## MCP server

The plugin declares the Honeycomb MCP server (`mcp.json`). You can also configure
it independently — see
[Honeycomb Docs: MCP Configuration](https://docs.honeycomb.io/integrations/mcp/configuration-guide/).
The `/honeycomb-setup` command walks through configuration interactively.

See [Cursor: Plugins](https://cursor.com/docs/plugins) for the underlying plugin
system.
