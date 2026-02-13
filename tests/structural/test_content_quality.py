"""Content quality tests — structural checks only.

Keyword-presence tests (AVG-near-latency, cross-references, agent-has-rate-limit)
were removed because they test the map, not the territory. Actual agent behavior
is validated by the skill-pressure and scenario test suites which run real LLM
invocations under realistic prompts.

What remains here: checks that prevent silent runtime failures (bad time_range
values, bloated skills, or non-discoverable descriptions).
"""

import re

import pytest

from tests.conftest import PLUGIN_ROOT, SKILLS_DIR, parse_frontmatter
from tests.constants import REQUIRED_SKILLS

# Maximum lines for a main SKILL.md file (progressive disclosure target)
MAX_SKILL_LINES = 500


def test_query_specs_use_human_readable_time():
    """time_range values in JSON examples should be strings, not large integers."""
    errors = []
    for md in sorted(PLUGIN_ROOT.rglob("*.md")):
        for match in re.finditer(r'"time_range"\s*:\s*(\d+)', md.read_text()):
            if int(match.group(1)) > 100:
                errors.append(str(md.relative_to(PLUGIN_ROOT)))
    assert not errors, f"Non-human-readable time_range in: {errors}"


@pytest.mark.parametrize("skill_name", REQUIRED_SKILLS)
def test_skill_description_starts_with_action(skills_dir, skill_name):
    """Skill descriptions lead with action-oriented language for discovery.

    Per the Writing Claude Directives guide, descriptions should start with
    'Use when...' to put triggering context first for skill matching.
    """
    fm = parse_frontmatter(skills_dir / skill_name / "SKILL.md")
    assert fm is not None, f"{skill_name}/SKILL.md has no YAML frontmatter"
    desc = fm.get("description", "").strip()
    assert desc.lower().startswith("use when"), (
        f"{skill_name} description should start with 'Use when...' "
        f"(got: '{desc[:50]}...')"
    )


@pytest.mark.parametrize("skill_name", REQUIRED_SKILLS)
def test_skill_line_count_within_budget(skills_dir, skill_name):
    """Main SKILL.md files stay under {MAX_SKILL_LINES} lines.

    Keeps frequently-loaded directives concise; detailed content belongs in
    references/ files.
    """.format(MAX_SKILL_LINES=MAX_SKILL_LINES)
    path = skills_dir / skill_name / "SKILL.md"
    line_count = len(path.read_text().splitlines())
    assert line_count <= MAX_SKILL_LINES, (
        f"{skill_name}/SKILL.md has {line_count} lines (max {MAX_SKILL_LINES}). "
        f"Move detailed content to references/ files."
    )
