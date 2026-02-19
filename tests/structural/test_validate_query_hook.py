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


def _write_complete_marker(cache_dir: str, env_slug: str, dataset_slug: str, session_id: str = "test"):
    """Mark a cache as complete (built from get_dataset_columns, not find_columns)."""
    schema_dir = os.path.join(cache_dir, "honeycomb-schema", session_id)
    os.makedirs(schema_dir, exist_ok=True)
    marker = os.path.join(schema_dir, f"{env_slug}--{dataset_slug}.complete")
    with open(marker, "w") as f:
        f.write("get_dataset_columns\n")


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
            _write_complete_marker(tmpdir, "prod", "api-requests")
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
            _write_complete_marker(tmpdir, "prod", "api-requests")
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
            _write_complete_marker(tmpdir, "prod", "api-requests")
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
            _write_complete_marker(tmpdir, "prod", "api-requests")
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
            _write_complete_marker(tmpdir, "prod", "api-requests")
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
            _write_complete_marker(tmpdir, "prod", "api-requests")
            data = _make_input(query_spec={
                "calculations": [{"op": "AVG", "column": "unknown.calc.col"}],
            })
            result = _run_hook(data, cache_dir=tmpdir)
            assert result is not None
            assert "unknown.calc.col" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_column_from_filters(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "api-requests", ["known.col"])
            _write_complete_marker(tmpdir, "prod", "api-requests")
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
            _write_complete_marker(tmpdir, "prod", "api-requests")
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
            _write_complete_marker(tmpdir, "prod", "api-requests")
            data = _make_input(query_spec={
                "calculations": [{"op": "COUNT"}],
                "orders": [{"column": "unknown.order.col", "op": "COUNT"}],
            })
            result = _run_hook(data, cache_dir=tmpdir)
            assert result is not None
            assert "unknown.order.col" in result["hookSpecificOutput"]["permissionDecisionReason"]


# ── Bug 2: Named calculations and formulas in orders ────────────────────


class TestNamedCalculationsInOrders:
    """Orders can reference named calculations or formula names, not just columns.

    The hook should recognize these as query-local names and skip validation.
    See: honeycomb-plugin-validation-bug.md Bug 2.
    """

    def test_order_by_named_calculation(self):
        """Ordering by a named calculation should not be denied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "api-requests", ["error", "http.route"])
            data = _make_input(query_spec={
                "calculations": [
                    {"op": "COUNT", "name": "total"},
                    {"op": "COUNT", "name": "errors"},
                ],
                "breakdowns": ["http.route"],
                "orders": [{"column": "total", "order": "descending"}],
            })
            result = _run_hook(data, cache_dir=tmpdir)
            assert result is None, (
                f"Named calculation 'total' should not be validated as a column. "
                f"Got: {result}"
            )

    def test_order_by_formula_name(self):
        """Ordering by a formula name should not be denied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "api-requests", ["error", "http.route"])
            data = _make_input(query_spec={
                "calculations": [
                    {"op": "COUNT", "name": "total"},
                    {"op": "COUNT", "name": "errors"},
                ],
                "formulas": [
                    {"name": "error_rate", "expression": "$errors / $total * 100"},
                ],
                "breakdowns": ["http.route"],
                "orders": [{"column": "error_rate", "order": "descending"}],
            })
            result = _run_hook(data, cache_dir=tmpdir)
            assert result is None, (
                f"Formula name 'error_rate' should not be validated as a column. "
                f"Got: {result}"
            )

    def test_mixed_real_columns_and_named_calcs(self):
        """Real unknown columns should still be denied even when named calcs are present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "api-requests", ["http.route"])
            _write_complete_marker(tmpdir, "prod", "api-requests")
            data = _make_input(query_spec={
                "calculations": [
                    {"op": "COUNT", "name": "total"},
                    {"op": "AVG", "column": "nonexistent.col"},
                ],
                "orders": [{"column": "total", "order": "descending"}],
            })
            result = _run_hook(data, cache_dir=tmpdir)
            assert result is not None
            reason = result["hookSpecificOutput"]["permissionDecisionReason"]
            assert "nonexistent.col" in reason
            assert "total" not in reason, "Named calculation 'total' should not appear in deny reason"


# ── Bug 3: Calculated fields output names ────────────────────────────────


class TestCalculatedFields:
    """Calculated fields define derived columns that can be used elsewhere in the query.

    The hook should recognize calculated_fields[].name as query-local names.
    See: honeycomb-plugin-validation-bug.md Bug 3.
    """

    def test_calculated_field_name_in_breakdown(self):
        """A calculated field name used in breakdowns should not be denied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "api-requests", ["error", "http.status_code"])
            data = _make_input(query_spec={
                "calculations": [{"op": "COUNT"}],
                "calculated_fields": [
                    {"name": "error_pct", "expression": "MUL(IF($error, 1, 0), 100)"},
                ],
                "breakdowns": ["error_pct"],
            })
            result = _run_hook(data, cache_dir=tmpdir)
            assert result is None, (
                f"Calculated field name 'error_pct' should not be validated as a column. "
                f"Got: {result}"
            )

    def test_calculated_field_name_in_filter(self):
        """A calculated field name used in filters should not be denied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "api-requests", ["error"])
            data = _make_input(query_spec={
                "calculations": [{"op": "COUNT"}],
                "calculated_fields": [
                    {"name": "is_error", "expression": "IF($error, 1, 0)"},
                ],
                "filters": [{"column": "is_error", "op": "=", "value": 1}],
            })
            result = _run_hook(data, cache_dir=tmpdir)
            assert result is None, (
                f"Calculated field name 'is_error' should not be validated as a column. "
                f"Got: {result}"
            )

    def test_calculated_field_name_in_calculation(self):
        """A calculated field name used as a calculation column should not be denied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "api-requests", ["duration_ms"])
            data = _make_input(query_spec={
                "calculations": [{"op": "AVG", "column": "latency_bucket"}],
                "calculated_fields": [
                    {"name": "latency_bucket", "expression": "DIV($duration_ms, 100)"},
                ],
            })
            result = _run_hook(data, cache_dir=tmpdir)
            assert result is None, (
                f"Calculated field name 'latency_bucket' should not be validated as a column. "
                f"Got: {result}"
            )

    def test_real_unknown_column_still_denied_with_calculated_fields(self):
        """Real unknown columns should still be denied alongside calculated fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "api-requests", ["error"])
            _write_complete_marker(tmpdir, "prod", "api-requests")
            data = _make_input(query_spec={
                "calculations": [{"op": "AVG", "column": "bogus.column"}],
                "calculated_fields": [
                    {"name": "error_pct", "expression": "MUL(IF($error, 1, 0), 100)"},
                ],
                "breakdowns": ["error_pct"],
            })
            result = _run_hook(data, cache_dir=tmpdir)
            assert result is not None
            reason = result["hookSpecificOutput"]["permissionDecisionReason"]
            assert "bogus.column" in reason
            assert "error_pct" not in reason, "Calculated field 'error_pct' should not appear in deny reason"


# ── Bug 1: Partial cache should soft-nudge, not hard-deny ────────────


class TestPartialCacheNudge:
    """When the cache was built from find_columns (no .complete marker), unknown
    columns should get a soft systemMessage nudge instead of a hard deny.

    This prevents false denials when find_columns only returned its top-50
    results and the queried column exists but wasn't in those results.
    See: honeycomb-plugin-validation-bug.md Bug 1.
    """

    def test_partial_cache_unknown_column_nudges(self):
        """Unknown column in partial cache → soft nudge, not hard deny."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "api-requests", ["http.status_code", "http.route"])
            # No _write_complete_marker — this is a partial cache
            data = _make_input(query_spec={
                "calculations": [{"op": "COUNT"}],
                "breakdowns": ["app.user_id"],
            })
            result = _run_hook(data, cache_dir=tmpdir)
            assert result is not None, "Should produce output for unknown column"
            assert "systemMessage" in result, (
                f"Partial cache should soft-nudge, not hard-deny. Got: {result}"
            )
            assert "hookSpecificOutput" not in result, (
                f"Partial cache should not produce a deny decision. Got: {result}"
            )

    def test_partial_cache_known_column_passes(self):
        """Known column in partial cache → silent pass (no change from before)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "api-requests", ["http.status_code", "http.route"])
            data = _make_input(query_spec={
                "calculations": [{"op": "COUNT"}],
                "breakdowns": ["http.route"],
            })
            assert _run_hook(data, cache_dir=tmpdir) is None

    def test_partial_cache_nudge_includes_column_names(self):
        """The nudge message should mention which columns couldn't be verified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "api-requests", ["http.status_code"])
            data = _make_input(query_spec={
                "calculations": [{"op": "COUNT"}],
                "breakdowns": ["app.user_id", "http.status_code"],
            })
            result = _run_hook(data, cache_dir=tmpdir)
            assert result is not None
            msg = result["systemMessage"]
            assert "app.user_id" in msg, "Nudge should mention the unverified column"

    def test_partial_cache_nudge_includes_suggestions(self):
        """Even in nudge mode, fuzzy suggestions help catch typos."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "api-requests", ["http.status_code", "http.route", "http.method"])
            data = _make_input(query_spec={
                "calculations": [{"op": "COUNT"}],
                "breakdowns": ["http.staus_code"],
            })
            result = _run_hook(data, cache_dir=tmpdir)
            assert result is not None
            msg = result["systemMessage"]
            assert "http.status_code" in msg, "Nudge should include fuzzy suggestion for typo"

    def test_complete_cache_still_denies(self):
        """With .complete marker, unknown columns are still hard-denied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "api-requests", ["http.status_code", "http.route"])
            _write_complete_marker(tmpdir, "prod", "api-requests")
            data = _make_input(query_spec={
                "calculations": [{"op": "COUNT"}],
                "breakdowns": ["app.user_id"],
            })
            result = _run_hook(data, cache_dir=tmpdir)
            assert result is not None
            assert "hookSpecificOutput" in result
            assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_upgraded_cache_denies_after_get_dataset_columns(self):
        """If find_columns ran first, then get_dataset_columns added the marker,
        the cache should be treated as complete → hard deny."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Simulate: find_columns built partial cache
            _write_cache(tmpdir, "prod", "api-requests", ["http.status_code"])
            # Then get_dataset_columns added more columns + marker
            _write_cache(tmpdir, "prod", "api-requests", ["http.status_code", "http.route", "http.method"])
            _write_complete_marker(tmpdir, "prod", "api-requests")
            data = _make_input(query_spec={
                "calculations": [{"op": "COUNT"}],
                "breakdowns": ["nonexistent.column"],
            })
            result = _run_hook(data, cache_dir=tmpdir)
            assert result is not None
            assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_partial_all_cache_nudges(self):
        """Partial _all cache should also soft-nudge, not hard-deny."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_cache(tmpdir, "prod", "_all", ["http.route", "http.status_code"])
            # No complete marker on _all
            data = _make_input(query_spec={
                "calculations": [{"op": "COUNT"}],
                "breakdowns": ["app.user_id"],
            })
            result = _run_hook(data, cache_dir=tmpdir)
            assert result is not None
            assert "systemMessage" in result, (
                f"Partial _all cache should soft-nudge. Got: {result}"
            )
