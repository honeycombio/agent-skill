"""Plugin manifest and directory layout tests."""

import json
import re

import pytest

from tests.conftest import PLUGIN_ROOT, PRODUCT_MARKETPLACE_JSONS, PRODUCT_PLUGIN_JSONS, REPO_ROOT
from tests.constants import REQUIRED_SKILLS


def test_plugin_json(plugin_json_path):
    """plugin.json exists, is valid, and has required fields."""
    assert plugin_json_path.exists(), f"plugin.json not found at {plugin_json_path}"
    data = json.loads(plugin_json_path.read_text())
    assert data["name"] == "honeycomb"
    for field in ("version", "description"):
        assert data.get(field), f"plugin.json field '{field}' is missing or empty"
    parts = data["version"].split(".")
    assert len(parts) == 3 and all(p.isdigit() for p in parts), (
        f"Version should be semver, got: {data['version']}"
    )


@pytest.mark.parametrize("skill_name", REQUIRED_SKILLS)
def test_skill_layout(skills_dir, skill_name):
    """Each skill has SKILL.md and a non-empty references/ directory."""
    assert (skills_dir / skill_name / "SKILL.md").is_file(), (
        f"SKILL.md missing for: {skill_name}"
    )
    refs = list((skills_dir / skill_name / "references").glob("*.md"))
    assert refs, f"No reference files in {skill_name}/references/"


def test_agents_exist(agent_md_files):
    assert agent_md_files, "No agent .md files found"


def test_commands_exist(command_md_files):
    assert command_md_files, "No command .md files found"


def test_no_unexpected_top_level_dirs(plugin_root):
    expected = {
        ".claude-plugin",
        ".cursor-plugin",
        ".codex-plugin",
        "skills",
        "agents",
        "commands",
        "hooks",
        "assets",
    }
    actual = {p.name for p in plugin_root.iterdir() if p.is_dir()}
    unexpected = actual - expected
    assert not unexpected, f"Unexpected top-level directories: {unexpected}"


@pytest.mark.parametrize("product,path", PRODUCT_PLUGIN_JSONS.items())
def test_product_plugin_jsons(product, path):
    """Each supported product has a valid manifest for the shared plugin root."""
    assert path.exists(), f"{product} plugin manifest not found at {path}"
    data = json.loads(path.read_text())
    assert data["name"] == "honeycomb"
    for field in ("version", "description"):
        assert data.get(field), f"{product} plugin.json field '{field}' is missing or empty"


@pytest.mark.parametrize("product,path", PRODUCT_MARKETPLACE_JSONS.items())
def test_product_marketplace_jsons(product, path):
    """Each supported product has a repo-level marketplace entry for honeycomb/."""
    assert path.exists(), f"{product} marketplace not found at {path}"
    data = json.loads(path.read_text())
    assert data["name"] == "honeycomb-plugins"
    assert isinstance(data["plugins"], list), f"{product} plugins must be a list"
    assert any(entry["name"] == "honeycomb" for entry in data["plugins"])


def test_codex_marketplace_entry_shape():
    """Codex marketplace entries include install policy metadata."""
    data = json.loads(PRODUCT_MARKETPLACE_JSONS["codex"].read_text())
    entry = next(item for item in data["plugins"] if item["name"] == "honeycomb")
    assert entry["source"] == {"source": "local", "path": "./honeycomb"}
    assert entry["policy"]["installation"] == "AVAILABLE"
    assert entry["policy"]["authentication"] == "ON_INSTALL"
    assert entry["category"]
    assert (REPO_ROOT / entry["source"]["path"]).resolve().is_dir()


def test_cursor_marketplace_source_shape():
    """Cursor marketplace source is relative to the repo root."""
    data = json.loads(PRODUCT_MARKETPLACE_JSONS["cursor"].read_text())
    entry = next(item for item in data["plugins"] if item["name"] == "honeycomb")
    assert entry["source"] == "honeycomb"
    assert (REPO_ROOT / entry["source"]).resolve().is_dir()


def test_product_mcp_configs():
    """Claude/Codex and Cursor load MCP from their product-specific filenames."""
    claude_codex = json.loads((PLUGIN_ROOT / ".mcp.json").read_text())
    cursor = json.loads((PLUGIN_ROOT / "mcp.json").read_text())
    assert claude_codex["honeycomb"]["type"] == "http"
    assert claude_codex["honeycomb"]["url"].startswith("https://mcp.honeycomb.io/")
    assert cursor["mcpServers"]["honeycomb"] == claude_codex["honeycomb"]


def test_marketplace_json_exists(marketplace_json_path):
    """marketplace.json exists at repo root."""
    assert marketplace_json_path.exists(), (
        f"marketplace.json not found at {marketplace_json_path}"
    )


def test_marketplace_json_valid(marketplace_json_path):
    """marketplace.json is valid JSON with required fields."""
    data = json.loads(marketplace_json_path.read_text())
    for field in ("name", "version", "owner", "plugins"):
        assert field in data, f"marketplace.json missing required field: {field}"
    assert isinstance(data["plugins"], list), "plugins must be a list"
    assert len(data["plugins"]) > 0, "plugins list must not be empty"


def test_marketplace_plugin_source_exists(marketplace_json_path):
    """Each plugin source path in marketplace.json points to an existing directory."""
    data = json.loads(marketplace_json_path.read_text())
    for plugin in data["plugins"]:
        source = plugin.get("source", "")
        repo_root = marketplace_json_path.parent.parent
        resolved = (repo_root / source).resolve()
        assert resolved.is_dir(), (
            f"Plugin source '{source}' does not resolve to a directory: {resolved}"
        )


def test_marketplace_version_matches_plugin_json(marketplace_json_path, plugin_json_path):
    """Plugin version in marketplace.json matches plugin.json (single source of truth)."""
    marketplace = json.loads(marketplace_json_path.read_text())
    plugin = json.loads(plugin_json_path.read_text())
    for entry in marketplace["plugins"]:
        if entry["name"] == plugin["name"]:
            assert entry["version"] == plugin["version"], (
                f"Version mismatch: marketplace.json has {entry['version']}, "
                f"plugin.json has {plugin['version']}"
            )
            break
    else:
        pytest.fail(
            f"Plugin '{plugin['name']}' not found in marketplace.json plugins list"
        )


def test_codeowners_exists(codeowners_path):
    """CODEOWNERS file exists at .github/CODEOWNERS."""
    assert codeowners_path.exists(), f"CODEOWNERS not found at {codeowners_path}"


@pytest.mark.parametrize("skill_name", REQUIRED_SKILLS)
def test_skill_has_codeowners_entry(codeowners_entries, skill_name):
    """Every skill directory must have an entry in .github/CODEOWNERS."""
    pattern = f"honeycomb/skills/{skill_name}/"
    assert any(line.startswith(pattern) for line in codeowners_entries), (
        f"No CODEOWNERS entry found for skill '{skill_name}'. "
        f"Add a line starting with '{pattern}' to .github/CODEOWNERS."
    )


def test_skill_reference_paths_use_plugin_root(skill_md_files):
    """All references/ paths in SKILL.md files must use ${CLAUDE_PLUGIN_ROOT} prefix."""
    bare_ref_pattern = re.compile(r"`references/")
    violations = []
    for path in skill_md_files:
        content = path.read_text()
        for lineno, line in enumerate(content.splitlines(), 1):
            if bare_ref_pattern.search(line):
                violations.append(f"{path.name}:{lineno}: {line.strip()}")
    assert not violations, (
        "Found bare references/ paths without ${CLAUDE_PLUGIN_ROOT} prefix:\n"
        + "\n".join(violations)
    )
