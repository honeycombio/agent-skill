"""Verify all MCP tool name references in plugin content match real tools."""

import re

from tests.conftest import PLUGIN_ROOT, SKILLS_DIR
from tests.constants import REQUIRED_SKILLS, TOOL_CATEGORIES, VALID_MCP_TOOLS

# Pattern to find backtick-quoted tool names that look like MCP tools
TOOL_REF_PATTERN = re.compile(
    r"`((?:get_|run_|find_|create_|list_)\w+|feedback)`"
)

# Negated references (mentioned as wrong/absent)
NEGATED_TOOL_PATTERN = re.compile(
    r"not\s+`((?:get_|run_|find_|create_|list_)\w+|feedback)`"
)


def _extract_tool_refs(text: str, exclude_negated: bool = False) -> set[str]:
    refs = set(TOOL_REF_PATTERN.findall(text))
    if exclude_negated:
        refs -= set(NEGATED_TOOL_PATTERN.findall(text))
    return refs


def test_all_referenced_tools_are_valid():
    """Every tool name referenced in the plugin is a real MCP tool."""
    all_refs = set()
    for md in PLUGIN_ROOT.rglob("*.md"):
        all_refs |= _extract_tool_refs(md.read_text(), exclude_negated=True)
    invalid = all_refs - VALID_MCP_TOOLS
    assert not invalid, f"Invalid tool names referenced: {sorted(invalid)}"


def test_key_tools_in_skills():
    """Essential tools (workspace context, find_columns, run_query) appear in skill trees."""
    essential = {"get_workspace_context", "find_columns", "run_query"}
    skill_refs = set()
    for skill_name in REQUIRED_SKILLS:
        skill_dir = SKILLS_DIR / skill_name
        for md in skill_dir.rglob("*.md"):
            skill_refs |= _extract_tool_refs(md.read_text())
    missing = essential - skill_refs
    assert not missing, f"Essential tools missing from skills: {sorted(missing)}"


def test_agent_covers_all_tool_categories():
    """The agent references tools from every category (context, query, trace, reliability, boards)."""
    agent_refs = set()
    for md in (PLUGIN_ROOT / "agents").glob("*.md"):
        agent_refs |= _extract_tool_refs(md.read_text())
    missing = [cat for cat, tools in TOOL_CATEGORIES.items() if not agent_refs & tools]
    assert not missing, f"Agent missing tool refs for categories: {missing}"
