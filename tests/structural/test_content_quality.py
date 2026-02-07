"""Best practice and content quality enforcement tests."""

import re

from tests.conftest import PLUGIN_ROOT, SKILLS_DIR
from tests.constants import REQUIRED_SKILLS


def _read_all_skill_content() -> dict[str, str]:
    """Return {skill_name: full_text} for all skills (SKILL.md + references)."""
    result = {}
    for skill_name in REQUIRED_SKILLS:
        parts = [md.read_text() for md in sorted((SKILLS_DIR / skill_name).rglob("*.md"))]
        result[skill_name] = "\n".join(parts)
    return result


ALL_SKILL_CONTENT = _read_all_skill_content()


def test_query_skills_prime_context():
    """Skills that reference run_query also reference a context-priming tool."""
    context_tools = {"get_workspace_context", "find_columns", "get_dataset_columns"}
    pattern = re.compile(r"`(?:" + "|".join(context_tools) + r")`")
    for skill_name in REQUIRED_SKILLS:
        text = (SKILLS_DIR / skill_name / "SKILL.md").read_text()
        if "`run_query`" in text:
            assert pattern.search(text), (
                f"{skill_name} references run_query but no context-priming tool"
            )


def test_no_avg_for_latency_without_caveat():
    """If AVG is mentioned near latency, surrounding text must discourage it."""
    caveat_words = {"never", "instead", "prefer", "not", "don't", "avoid", "hides"}
    for skill_name, text in ALL_SKILL_CONTENT.items():
        lines = text.split("\n")
        for i, line in enumerate(lines):
            lower = line.lower()
            if "avg" in lower and "latency" in lower:
                context = "\n".join(lines[max(0, i - 2):i + 3]).lower()
                assert any(w in context for w in caveat_words), (
                    f"{skill_name}: AVG + latency without caveat: {line.strip()}"
                )


def test_query_specs_use_human_readable_time():
    """time_range values in JSON examples should be strings, not large integers."""
    errors = []
    for md in sorted(PLUGIN_ROOT.rglob("*.md")):
        for match in re.finditer(r'"time_range"\s*:\s*(\d+)', md.read_text()):
            if int(match.group(1)) > 100:
                errors.append(str(md.relative_to(PLUGIN_ROOT)))
    assert not errors, f"Non-human-readable time_range in: {errors}"


def test_skills_cross_reference_each_other():
    """At least 2 skills mention another skill by name."""
    count = 0
    for skill_name in REQUIRED_SKILLS:
        text = (SKILLS_DIR / skill_name / "SKILL.md").read_text()
        others = [s for s in REQUIRED_SKILLS if s != skill_name]
        if any(other in text for other in others):
            count += 1
    assert count >= 2, f"Only {count} skills cross-reference others (need 2+)"


def test_agent_quality():
    """Agent has step-by-step workflow and mentions rate limiting."""
    for md in (PLUGIN_ROOT / "agents").glob("*.md"):
        text = md.read_text()
        assert "Step 1" in text or "step 1" in text.lower(), (
            f"{md.name} missing investigation workflow"
        )
        assert "rate limit" in text.lower() or "rate-limit" in text.lower(), (
            f"{md.name} doesn't mention rate limiting"
        )
