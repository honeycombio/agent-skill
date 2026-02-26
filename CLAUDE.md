# Honeycomb Agent Skill — Development Guide

## Repository Structure

This repo contains a single Claude Code plugin at `honeycomb/`. The root also has a marketplace manifest at `.claude-plugin/marketplace.json` and test infrastructure under `tests/`.

```
honeycomb/                    # Plugin root
  .claude-plugin/plugin.json  # Plugin manifest
  skills/                     # 8 skill directories, each with SKILL.md + references/
  agents/                     # Agent definitions (.md)
  commands/                   # Slash commands (.md)
  hooks/                      # hooks.json + scripts/ for query validation
```

## Key Conventions

- All versions (plugin.json, marketplace.json, skill metadata) must stay in sync
- Skill frontmatter must include `name`, `description`, and `metadata.version`
- All intra-plugin paths use `${CLAUDE_PLUGIN_ROOT}`, never hardcoded paths
- Skills use `allowed-tools` (hyphenated), not `allowed_tools`
- Hook scripts must fail open (`exit 0`) on errors

## Tests

```bash
python -m venv .venv && source .venv/bin/activate
make install   # installs test deps including skills-ref
make test      # runs structural tests only
```

Structural tests verify:
- Plugin manifest, marketplace manifest, and directory layout
- YAML frontmatter presence and required fields in all components
- Version consistency across plugin.json and marketplace.json
- The validate-query.sh hook behavior (subprocess-based unit tests)

The `tests/scenarios/` and `tests/skill-pressure/` suites require a Honeycomb API key and are not part of the default `make test` target.

## Adding a New Skill

1. Create `honeycomb/skills/<skill-name>/SKILL.md` with frontmatter:
   ```yaml
   ---
   name: skill-name
   description: >
     What this skill does. Trigger phrases: "phrase1", "phrase2", ...
   metadata:
     version: "1.0.0"
   ---
   ```
2. Add reference files in `honeycomb/skills/<skill-name>/references/`
3. Add the skill name to `REQUIRED_SKILLS` in `tests/constants.py`
4. Run `make test` to verify structure

## Hook System

The plugin uses two hooks for query validation:
- **PostToolUse** (`cache-columns.sh`): Caches column names from `find_columns`/`get_dataset_columns`/`get_dataset` results
- **PreToolUse** (`validate-query.sh`): Validates query columns against the cache before `run_query` runs

The cache distinguishes partial (from `find_columns`, top-50 only) from complete (from `get_dataset_columns`) schemas. Partial caches produce soft nudges; complete caches produce hard denies for unknown columns.
