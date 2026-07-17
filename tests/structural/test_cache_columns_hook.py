"""Tests for the cache-columns.sh PostToolUse hook.

Exercises the hook by piping a find_columns / get_dataset_columns tool result
via subprocess and checking the per-session schema cache it writes — column
contents and, critically, when it marks the cache `.complete`.

The `.complete` marker tells validate-query.sh the cache is the authoritative
full schema. get_dataset_columns paginates, so the marker must only appear once
every page has actually been cached — otherwise validate-query firmly nudges
against columns that live on un-fetched pages.
"""

import json
import os
import subprocess

import pytest

from tests.conftest import PLUGIN_ROOT

SCRIPT = PLUGIN_ROOT / "hooks" / "scripts" / "cache-columns.sh"


def _columns_result(columns: list[str], page: int = 1, total_pages: int = 1, with_metadata: bool = True) -> str:
    """Build a markdown column-table tool result, optionally with a Metadata block."""
    lines = ["# Columns", "", "| Name | Type | Description |", "| --- | --- | --- |"]
    lines += [f"| {c} | string |  |" for c in columns]
    text = "\n".join(lines)
    if with_metadata:
        text += (
            "\n\n---\nMetadata:\n"
            "  dataset: api-requests\n"
            "  environment: prod\n"
            "  items_per_page: 1000\n"
            f"  page: {page}\n"
            f"  total_items: {len(columns)}\n"
            f"  total_pages: {total_pages}\n"
            "---\n"
        )
    return text


def _make_input(
    columns: list[str],
    tool: str = "get_dataset_columns",
    env_slug: str = "prod",
    dataset_slug: str = "api-requests",
    session_id: str = "test",
    page: int = 1,
    total_pages: int = 1,
    with_metadata: bool = True,
) -> dict:
    return {
        "session_id": session_id,
        "tool_name": f"mcp__honeycomb__{tool}",
        "tool_input": {"environment_slug": env_slug, "dataset_slug": dataset_slug},
        "tool_response": {
            "content": [
                {
                    "type": "text",
                    "text": _columns_result(columns, page, total_pages, with_metadata),
                }
            ],
            "isError": False,
        },
    }


def _run_hook(input_data: dict, cache_dir: str):
    env = os.environ.copy()
    env["TMPDIR"] = cache_dir
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    assert result.returncode == 0, f"Hook exited {result.returncode}: {result.stderr}"
    return result


def _paths(cache_dir: str, env_slug: str = "prod", dataset_slug: str = "api-requests", session_id: str = "test"):
    base = os.path.join(cache_dir, "honeycomb-schema", session_id, f"{env_slug}--{dataset_slug}")
    return f"{base}.txt", f"{base}.complete"


def _cached_columns(cache_file: str) -> list[str]:
    with open(cache_file) as f:
        return [line.strip() for line in f if line.strip()]


# ── Column extraction + caching ─────────────────────────────────────────


class TestColumnCaching:
    def test_columns_written_to_cache(self, tmp_path):
        _run_hook(_make_input(["http.route", "http.status_code"]), str(tmp_path))
        cache_file, _ = _paths(str(tmp_path))
        assert sorted(_cached_columns(cache_file)) == ["http.route", "http.status_code"]

    def test_legacy_content_block_array_is_supported(self, tmp_path):
        data = _make_input(["http.route"])
        data["tool_response"] = data["tool_response"]["content"]
        _run_hook(data, str(tmp_path))
        cache_file, _ = _paths(str(tmp_path))
        assert _cached_columns(cache_file) == ["http.route"]

    def test_unknown_tool_response_shape_fails_open(self, tmp_path):
        data = _make_input(["http.route"])
        data["tool_response"] = {"structuredContent": {"columns": ["http.route"]}}
        _run_hook(data, str(tmp_path))
        cache_file, _ = _paths(str(tmp_path))
        assert not os.path.exists(cache_file)

    def test_appends_and_dedupes_across_calls(self, tmp_path):
        _run_hook(_make_input(["http.route"]), str(tmp_path))
        _run_hook(_make_input(["http.route", "http.method"]), str(tmp_path))
        cache_file, _ = _paths(str(tmp_path))
        assert sorted(_cached_columns(cache_file)) == ["http.method", "http.route"]

    def test_no_dataset_uses_all_cache(self, tmp_path):
        data = _make_input(["svc.name"], dataset_slug="")
        del data["tool_input"]["dataset_slug"]
        _run_hook(data, str(tmp_path))
        cache_file, _ = _paths(str(tmp_path), dataset_slug="_all")
        assert _cached_columns(cache_file) == ["svc.name"]


# ── find_columns → partial (never complete) ─────────────────────────────


class TestFindColumnsPartial:
    def test_find_columns_does_not_mark_complete(self, tmp_path):
        _run_hook(_make_input(["http.route"], tool="find_columns"), str(tmp_path))
        cache_file, marker = _paths(str(tmp_path))
        assert os.path.exists(cache_file)
        assert not os.path.exists(marker), "find_columns cache must remain partial"


# ── get_dataset_columns completeness (pagination-aware) ─────────────────


class TestCompletenessMarker:
    def test_single_page_marks_complete(self, tmp_path):
        _run_hook(_make_input(["http.route", "http.method"], total_pages=1), str(tmp_path))
        _, marker = _paths(str(tmp_path))
        assert os.path.exists(marker), "A single-page schema is complete"

    def test_missing_metadata_defaults_to_complete(self, tmp_path):
        # get_dataset_columns always includes metadata; if absent we fall back to
        # single-page (complete), matching the pre-pagination behavior.
        _run_hook(_make_input(["http.route"], with_metadata=False), str(tmp_path))
        _, marker = _paths(str(tmp_path))
        assert os.path.exists(marker)

    def test_first_of_two_pages_not_complete(self, tmp_path):
        _run_hook(_make_input(["a.col", "b.col"], page=1, total_pages=2), str(tmp_path))
        cache_file, marker = _paths(str(tmp_path))
        assert _cached_columns(cache_file) == ["a.col", "b.col"]
        assert not os.path.exists(marker), "Page 1 of 2 is not the full schema"

    def test_complete_only_after_all_pages_cached(self, tmp_path):
        _run_hook(_make_input(["a.col"], page=1, total_pages=2), str(tmp_path))
        _, marker = _paths(str(tmp_path))
        assert not os.path.exists(marker)
        _run_hook(_make_input(["b.col"], page=2, total_pages=2), str(tmp_path))
        cache_file, marker = _paths(str(tmp_path))
        assert os.path.exists(marker), "All pages cached → complete"
        assert sorted(_cached_columns(cache_file)) == ["a.col", "b.col"]

    def test_refetching_same_page_does_not_complete(self, tmp_path):
        # Distinct pages, not call count, drive completeness.
        _run_hook(_make_input(["a.col"], page=1, total_pages=2), str(tmp_path))
        _run_hook(_make_input(["a.col"], page=1, total_pages=2), str(tmp_path))
        _, marker = _paths(str(tmp_path))
        assert not os.path.exists(marker), "Same page twice is still only one of two pages"

    def test_page_field_not_confused_with_items_per_page(self, tmp_path):
        """`items_per_page: 1000` must not be read as the current page.

        Fetch page 2 then page 1 of a 2-page schema; completeness must require
        both distinct pages, which only works if `page:` is parsed correctly.
        """
        _run_hook(_make_input(["b.col"], page=2, total_pages=2), str(tmp_path))
        _, marker = _paths(str(tmp_path))
        assert not os.path.exists(marker)
        _run_hook(_make_input(["a.col"], page=1, total_pages=2), str(tmp_path))
        _, marker = _paths(str(tmp_path))
        assert os.path.exists(marker)
