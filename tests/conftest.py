"""Shared fixtures for Honeycomb plugin structural tests."""

import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "honeycomb"
SKILLS_DIR = PLUGIN_ROOT / "skills"
AGENTS_DIR = PLUGIN_ROOT / "agents"
COMMANDS_DIR = PLUGIN_ROOT / "commands"
PLUGIN_JSON = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"


@pytest.fixture
def plugin_root():
    return PLUGIN_ROOT


@pytest.fixture
def skills_dir():
    return SKILLS_DIR


@pytest.fixture
def agents_dir():
    return AGENTS_DIR


@pytest.fixture
def commands_dir():
    return COMMANDS_DIR


@pytest.fixture
def plugin_json_path():
    return PLUGIN_JSON


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


@pytest.fixture
def all_md_files():
    """Return all .md files under the plugin directory."""
    return sorted(PLUGIN_ROOT.rglob("*.md"))


@pytest.fixture
def all_reference_files():
    """Return all reference .md files across all skills."""
    return sorted(SKILLS_DIR.glob("*/references/*.md"))


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
