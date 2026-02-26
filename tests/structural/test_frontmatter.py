"""YAML frontmatter validation for skills, agents, and commands.

Structural checks only: verifies required fields are present and valid.
Content quality (description wording, trigger phrase counts) is not tested here.
"""

import pytest
from skills_ref import validate as skills_ref_validate

from tests.conftest import parse_frontmatter
from tests.constants import REQUIRED_SKILLS


@pytest.mark.parametrize("skill_name", REQUIRED_SKILLS)
def test_skill_has_frontmatter(skills_dir, skill_name):
    """Skill SKILL.md has YAML frontmatter with required fields."""
    fm = parse_frontmatter(skills_dir / skill_name / "SKILL.md")
    assert fm is not None, f"{skill_name}/SKILL.md has no YAML frontmatter"
    assert fm.get("name"), f"{skill_name} frontmatter missing 'name'"
    metadata = fm.get("metadata", {})
    assert metadata.get("version"), f"{skill_name} frontmatter missing 'metadata.version'"
    assert fm.get("description"), f"{skill_name} frontmatter missing 'description'"


@pytest.mark.parametrize("skill_name", REQUIRED_SKILLS)
def test_skill_agentskills_spec(skills_dir, skill_name):
    """Skill passes agentskills.io specification validation (skills-ref)."""
    problems = skills_ref_validate(skills_dir / skill_name)
    assert not problems, f"{skill_name} failed skills-ref validation:\n" + "\n".join(
        f"  - {p}" for p in problems
    )


def test_agent_frontmatter(agent_md_files):
    """Agents have frontmatter with name and description."""
    for path in agent_md_files:
        fm = parse_frontmatter(path)
        assert fm is not None, f"{path.name} has no YAML frontmatter"
        assert fm.get("name"), f"{path.name} frontmatter missing 'name'"
        assert fm.get("description"), f"{path.name} frontmatter missing 'description'"


def test_command_frontmatter(command_md_files):
    """Commands have frontmatter with name and description."""
    for path in command_md_files:
        fm = parse_frontmatter(path)
        assert fm is not None, f"{path.name} has no YAML frontmatter"
        assert fm.get("name"), f"{path.name} frontmatter missing 'name'"
        assert fm.get("description"), f"{path.name} frontmatter missing 'description'"
