"""Plugin manifest and directory layout tests."""

import json

import pytest

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
    expected = {".claude-plugin", "skills", "agents", "commands"}
    actual = {p.name for p in plugin_root.iterdir() if p.is_dir()}
    unexpected = actual - expected
    assert not unexpected, f"Unexpected top-level directories: {unexpected}"
