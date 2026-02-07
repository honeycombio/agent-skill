"""YAML frontmatter validation for skills, agents, and commands."""

import re

import pytest

from tests.conftest import parse_frontmatter
from tests.constants import REQUIRED_SKILLS


@pytest.mark.parametrize("skill_name", REQUIRED_SKILLS)
def test_skill_frontmatter(skills_dir, skill_name):
    """Skill has frontmatter with name, description (50+ chars, 5+ trigger phrases), version."""
    fm = parse_frontmatter(skills_dir / skill_name / "SKILL.md")
    assert fm is not None, f"{skill_name}/SKILL.md has no YAML frontmatter"
    assert fm.get("name"), f"{skill_name} frontmatter missing 'name'"
    assert fm.get("version"), f"{skill_name} frontmatter missing 'version'"
    desc = fm.get("description", "")
    assert isinstance(desc, str) and len(desc) >= 50, (
        f"{skill_name} description too short ({len(desc)} chars, need 50+)"
    )
    quotes = re.findall(r'"[^"]{3,}"', desc)
    assert len(quotes) >= 5, (
        f"{skill_name} description has only {len(quotes)} trigger phrases (need 5+)"
    )


def test_agent_frontmatter(agent_md_files):
    """Agents have frontmatter with name, description containing examples."""
    for path in agent_md_files:
        fm = parse_frontmatter(path)
        assert fm is not None, f"{path.name} has no YAML frontmatter"
        assert fm.get("name"), f"{path.name} frontmatter missing 'name'"
        desc = fm.get("description", "")
        assert isinstance(desc, str) and desc, f"{path.name} missing description"
        assert "<example>" in desc, f"{path.name} description missing <example> blocks"


def test_command_frontmatter(command_md_files):
    """Commands have frontmatter with name and description."""
    for path in command_md_files:
        fm = parse_frontmatter(path)
        assert fm is not None, f"{path.name} has no YAML frontmatter"
        assert fm.get("name"), f"{path.name} frontmatter missing 'name'"
        assert fm.get("description"), f"{path.name} frontmatter missing 'description'"
