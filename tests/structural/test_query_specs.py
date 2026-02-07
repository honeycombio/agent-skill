"""Extract and validate all JSON query spec examples from plugin content."""

import json
import pathlib
import re

import jsonschema
import pytest

from tests.conftest import PLUGIN_ROOT
from tests.constants import OPS_FORBIDDING_COLUMN, OPS_REQUIRING_COLUMN

SCHEMA_PATH = pathlib.Path(__file__).resolve().parent.parent / "schemas" / "query_spec.schema.json"


def _extract_json_blocks(text: str) -> list[dict]:
    """Extract all ```json ... ``` blocks that parse as JSON objects."""
    blocks = []
    for match in re.finditer(r"```json\s*\n(.*?)```", text, re.DOTALL):
        raw = match.group(1).strip()
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                blocks.append(parsed)
        except json.JSONDecodeError:
            pass
    return blocks


def _collect_query_specs() -> list[tuple[str, dict]]:
    """Collect JSON blocks that look like query specs (have 'calculations' key)."""
    results = []
    for md in sorted(PLUGIN_ROOT.rglob("*.md")):
        rel = str(md.relative_to(PLUGIN_ROOT))
        for block in _extract_json_blocks(md.read_text()):
            if "calculations" in block:
                results.append((rel, block))
    return results


QUERY_SPECS = _collect_query_specs()


def test_json_blocks_parse():
    """All ```json blocks should parse without error."""
    errors = []
    for md in sorted(PLUGIN_ROOT.rglob("*.md")):
        text = md.read_text()
        for match in re.finditer(r"```json\s*\n(.*?)```", text, re.DOTALL):
            raw = match.group(1).strip()
            try:
                json.loads(raw)
            except json.JSONDecodeError as e:
                rel = str(md.relative_to(PLUGIN_ROOT))
                errors.append(f"{rel}: {e}")
    assert not errors, "JSON parse errors:\n" + "\n".join(errors)


def test_minimum_query_specs_found():
    """Sanity check: we should find at least 20 query spec examples."""
    assert len(QUERY_SPECS) >= 20, (
        f"Only found {len(QUERY_SPECS)} query spec blocks (expected 20+)"
    )


@pytest.mark.parametrize(
    "source,spec",
    QUERY_SPECS,
    ids=[f"{s}#{i}" for i, (s, _) in enumerate(QUERY_SPECS)],
)
def test_query_spec_schema(source, spec):
    """Query spec validates against JSON schema (covers op enums, filter ops, structure)."""
    schema = json.loads(SCHEMA_PATH.read_text())
    try:
        jsonschema.validate(spec, schema)
    except jsonschema.ValidationError as e:
        pytest.fail(f"{source}: {e.message}")


@pytest.mark.parametrize(
    "source,spec",
    QUERY_SPECS,
    ids=[f"{s}#{i}" for i, (s, _) in enumerate(QUERY_SPECS)],
)
def test_calc_column_requirements(source, spec):
    """Ops that need a column have one; ops that forbid a column don't."""
    for calc in spec["calculations"]:
        op = calc["op"]
        has_col = "column" in calc
        if op in OPS_REQUIRING_COLUMN:
            assert has_col, f"{source}: {op} requires a column"
        if op in OPS_FORBIDDING_COLUMN:
            assert not has_col, f"{source}: {op} must not have a column"
