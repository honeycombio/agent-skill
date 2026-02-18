"""Tests for the validate-query.sh PreToolUse hook.

Exercises the hook script by piping JSON input via subprocess and checking
the JSON output (or lack thereof) for correct validation behavior.
"""

import json
import os
import subprocess
import tempfile

import pytest

from tests.conftest import PLUGIN_ROOT

SCRIPT = PLUGIN_ROOT / "hooks" / "scripts" / "validate-query.sh"


def _run_hook(input_data: dict, cache_dir: str | None = None, session_id: str = "test") -> dict | None:
    """Run validate-query.sh with the given input and return parsed JSON output (or None)."""
    env = os.environ.copy()
    if cache_dir is not None:
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

    stdout = result.stdout.strip()
    if not stdout:
        return None
    return json.loads(stdout)


def _make_input(
    env_slug: str = "prod",
    dataset_slug: str = "api-requests",
    session_id: str = "test",
    query_spec: dict | None = None,
) -> dict:
    """Build a hook input payload."""
    return {
        "session_id": session_id,
        "tool_input": {
            "environment_slug": env_slug,
            "dataset_slug": dataset_slug,
            "query_spec": query_spec or {
                "calculations": [{"op": "COUNT"}],
                "time_range": 3600,
            },
        },
    }


def _write_cache(cache_dir: str, env_slug: str, dataset_slug: str, columns: list[str], session_id: str = "test"):
    """Write a schema cache file the hook can find."""
    schema_dir = os.path.join(cache_dir, "honeycomb-schema", session_id)
    os.makedirs(schema_dir, exist_ok=True)
    cache_file = os.path.join(schema_dir, f"{env_slug}--{dataset_slug}.txt")
    with open(cache_file, "w") as f:
        f.write("\n".join(sorted(columns)) + "\n")


# ── Fail-open: missing fields ────────────────────────────────────────────


class TestFailOpen:
    """Hook should exit silently (no output) when it can't validate."""

    def test_missing_env_slug(self):
        data = _make_input()
        data["tool_input"]["environment_slug"] = ""
        assert _run_hook(data) is None

    def test_missing_dataset_slug(self):
        data = _make_input()
        data["tool_input"]["dataset_slug"] = ""
        assert _run_hook(data) is None

    def test_missing_query_spec(self):
        data = _make_input()
        data["tool_input"].pop("query_spec")
        assert _run_hook(data) is None

    def test_no_columns_in_query(self):
        """COUNT has no column — nothing to validate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "api-requests", ["http.status_code"])
            data = _make_input(query_spec={"calculations": [{"op": "COUNT"}]})
            assert _run_hook(data, cache_dir=tmpdir) is None


# ── Soft nudge: no cache ────────────────────────────────────────────────


class TestNoCacheNudge:
    """When no schema cache exists, the hook should return a systemMessage nudge."""

    def test_nudge_when_no_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = _make_input(query_spec={
                "calculations": [{"op": "P99", "column": "duration_ms"}],
                "breakdowns": ["http.route"],
            })
            # duration_ms is well-known but http.route is not — needs cache
            result = _run_hook(data, cache_dir=tmpdir)
            assert result is not None
            assert "systemMessage" in result
            assert "api-requests" in result["systemMessage"]

    def test_nudge_still_sent_when_all_columns_wellknown(self):
        """Nudge fires based on missing cache, not per-column checks.

        The hook checks for a cache file before validating individual columns,
        so even if every column is well-known it still nudges when no cache
        exists. This is intentional — it encourages the model to populate the
        cache for future queries that may use non-well-known columns.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            data = _make_input(query_spec={
                "calculations": [{"op": "P99", "column": "duration_ms"}],
                "breakdowns": ["trace.trace_id"],
            })
            result = _run_hook(data, cache_dir=tmpdir)
            assert result is not None
            assert "systemMessage" in result


# ── Hard deny: column not in cache ──────────────────────────────────────


class TestDenyUnknownColumns:
    """When a cache exists and a column is missing, the hook should deny."""

    def test_deny_unknown_column(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "api-requests", ["http.status_code", "http.route"])
            data = _make_input(query_spec={
                "calculations": [{"op": "COUNT"}],
                "filters": [{"column": "htttp.status_code", "op": "=", "value": 200}],
            })
            result = _run_hook(data, cache_dir=tmpdir)
            assert result is not None
            deny = result["hookSpecificOutput"]
            assert deny["permissionDecision"] == "deny"
            assert "htttp.status_code" in deny["permissionDecisionReason"]

    def test_deny_includes_fuzzy_suggestions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "api-requests", ["http.status_code", "http.route", "http.method"])
            data = _make_input(query_spec={
                "calculations": [{"op": "COUNT"}],
                "breakdowns": ["http.staus_code"],
            })
            result = _run_hook(data, cache_dir=tmpdir)
            reason = result["hookSpecificOutput"]["permissionDecisionReason"]
            assert "http.status_code" in reason, "Expected fuzzy suggestion for typo"

    def test_deny_multiple_unknown_columns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "api-requests", ["http.status_code"])
            data = _make_input(query_spec={
                "calculations": [{"op": "AVG", "column": "latencyy"}],
                "breakdowns": ["userr.id"],
            })
            result = _run_hook(data, cache_dir=tmpdir)
            reason = result["hookSpecificOutput"]["permissionDecisionReason"]
            assert "latencyy" in reason
            assert "userr.id" in reason


# ── Valid columns pass ──────────────────────────────────────────────────


class TestValidColumns:
    """When all columns are in the cache, the hook should exit silently."""

    def test_all_columns_in_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "api-requests", ["http.status_code", "http.route", "http.method"])
            data = _make_input(query_spec={
                "calculations": [{"op": "COUNT"}],
                "breakdowns": ["http.route"],
                "filters": [{"column": "http.method", "op": "=", "value": "GET"}],
            })
            assert _run_hook(data, cache_dir=tmpdir) is None

    def test_mix_of_cached_and_wellknown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "api-requests", ["http.route"])
            data = _make_input(query_spec={
                "calculations": [{"op": "P99", "column": "duration_ms"}],
                "breakdowns": ["http.route", "name"],
            })
            assert _run_hook(data, cache_dir=tmpdir) is None


# ── Well-known columns ──────────────────────────────────────────────────


class TestWellKnownColumns:
    """Well-known columns always pass, even if not in cache."""

    @pytest.mark.parametrize("col", [
        "duration_ms", "trace.trace_id", "trace.span_id",
        "trace.parent_id", "error", "name", "service.name", "is_root",
    ])
    def test_wellknown_column_passes(self, col):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "api-requests", ["some.other.column"])
            data = _make_input(query_spec={
                "calculations": [{"op": "P99", "column": col}] if col != "name" else [{"op": "COUNT"}],
                "breakdowns": [col] if col == "name" else [],
            })
            assert _run_hook(data, cache_dir=tmpdir) is None


# ── Relational prefix stripping ─────────────────────────────────────────


class TestRelationalPrefixes:
    """Columns with any./root./parent./child./none. prefixes should be validated
    against the bare column name."""

    @pytest.mark.parametrize("prefix", ["any", "root", "none", "parent", "child"])
    def test_prefix_stripped_for_validation(self, prefix):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "api-requests", ["http.route"])
            data = _make_input(query_spec={
                "calculations": [{"op": "COUNT"}],
                "breakdowns": [f"{prefix}.http.route"],
            })
            assert _run_hook(data, cache_dir=tmpdir) is None

    def test_prefixed_unknown_column_denied(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "api-requests", ["http.route"])
            data = _make_input(query_spec={
                "calculations": [{"op": "COUNT"}],
                "breakdowns": ["any.nonexistent.column"],
            })
            result = _run_hook(data, cache_dir=tmpdir)
            assert result is not None
            assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


# ── Cross-dataset (_all) cache fallback ─────────────────────────────────


class TestAllDatasetFallback:
    """When no dataset-specific cache exists, the _all cache should be used."""

    def test_falls_back_to_all_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "_all", ["http.route", "http.status_code"])
            data = _make_input(query_spec={
                "calculations": [{"op": "COUNT"}],
                "breakdowns": ["http.route"],
            })
            assert _run_hook(data, cache_dir=tmpdir) is None

    def test_dataset_cache_preferred_over_all(self):
        """Dataset-specific cache should be used even if _all also exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # _all has the column, dataset-specific does not
            _write_cache(tmpdir, "prod", "_all", ["only.in.all"])
            _write_cache(tmpdir, "prod", "api-requests", ["http.route"])
            data = _make_input(query_spec={
                "calculations": [{"op": "COUNT"}],
                "breakdowns": ["only.in.all"],
            })
            result = _run_hook(data, cache_dir=tmpdir)
            assert result is not None
            assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


# ── Column extraction from all query_spec fields ────────────────────────


class TestColumnExtraction:
    """Columns should be validated from calculations, filters, breakdowns, and orders."""

    def test_column_from_calculations(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "api-requests", ["known.col"])
            data = _make_input(query_spec={
                "calculations": [{"op": "AVG", "column": "unknown.calc.col"}],
            })
            result = _run_hook(data, cache_dir=tmpdir)
            assert result is not None
            assert "unknown.calc.col" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_column_from_filters(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "api-requests", ["known.col"])
            data = _make_input(query_spec={
                "calculations": [{"op": "COUNT"}],
                "filters": [{"column": "unknown.filter.col", "op": "=", "value": "x"}],
            })
            result = _run_hook(data, cache_dir=tmpdir)
            assert result is not None
            assert "unknown.filter.col" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_column_from_breakdowns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "api-requests", ["known.col"])
            data = _make_input(query_spec={
                "calculations": [{"op": "COUNT"}],
                "breakdowns": ["unknown.breakdown.col"],
            })
            result = _run_hook(data, cache_dir=tmpdir)
            assert result is not None
            assert "unknown.breakdown.col" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_column_from_orders(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "api-requests", ["known.col"])
            data = _make_input(query_spec={
                "calculations": [{"op": "COUNT"}],
                "orders": [{"column": "unknown.order.col", "op": "COUNT"}],
            })
            result = _run_hook(data, cache_dir=tmpdir)
            assert result is not None
            assert "unknown.order.col" in result["hookSpecificOutput"]["permissionDecisionReason"]
