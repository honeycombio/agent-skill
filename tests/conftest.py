"""Shared fixtures for Honeycomb plugin structural tests."""

import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "honeycomb"
SKILLS_DIR = PLUGIN_ROOT / "skills"
AGENTS_DIR = PLUGIN_ROOT / "agents"
COMMANDS_DIR = PLUGIN_ROOT / "commands"
PLUGIN_JSON = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"
PRODUCT_PLUGIN_JSONS = {
    "claude": PLUGIN_ROOT / ".claude-plugin" / "plugin.json",
    "cursor": PLUGIN_ROOT / ".cursor-plugin" / "plugin.json",
    "codex": PLUGIN_ROOT / ".codex-plugin" / "plugin.json",
}
PRODUCT_MARKETPLACE_JSONS = {
    "claude": REPO_ROOT / ".claude-plugin" / "marketplace.json",
    "cursor": REPO_ROOT / ".cursor-plugin" / "marketplace.json",
    "codex": REPO_ROOT / ".agents" / "plugins" / "marketplace.json",
}


@pytest.fixture
def plugin_root():
    return PLUGIN_ROOT


@pytest.fixture
def skills_dir():
    return SKILLS_DIR


@pytest.fixture
def plugin_json_path():
    return PLUGIN_JSON


@pytest.fixture
def marketplace_json_path():
    return MARKETPLACE_JSON


@pytest.fixture
def skill_md_files():
    """Return all SKILL.md files."""
    return sorted(SKILLS_DIR.glob("*/SKILL.md"))


@pytest.fixture
def agent_md_files():
    """Return all agent .md files."""
    return sorted(AGENTS_DIR.glob("*.md"))


@pytest.fixture
def command_md_files():
    """Return all command .md files."""
    return sorted(COMMANDS_DIR.glob("*.md"))


def parse_frontmatter(path: pathlib.Path) -> dict | None:
    """Parse YAML frontmatter from a markdown file.

    Returns the parsed dict, or None if no frontmatter found.
    """
    import yaml

    text = path.read_text()
    if not text.startswith("---"):
        return None
    end = text.index("---", 3)
    return yaml.safe_load(text[3:end])
