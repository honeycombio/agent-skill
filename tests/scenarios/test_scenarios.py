"""Pytest entry point for scenario tests.

Requires:
  - claude CLI installed and on PATH
  - Honeycomb MCP server configured (via .mcp.json or env)
  - ANTHROPIC_API_KEY set

Run: make test-scenarios       (comparison: plugin vs MCP-only, core subset)
     make test-scenarios-full   (comparison: plugin vs MCP-only, all scenarios)
     make test-plugin-only      (plugin-only, no baseline)
     make test-single ID=trigger-slow-endpoints
"""

import json
import shutil
from pathlib import Path

import pytest
import yaml

from .comparator import compare, REGRESSION_THRESHOLD
from .evaluator import evaluate
from .report import parse_ndjson, detect_skill_usage
from .runner import run_scenario, OUTPUT_DIR

DEFINITIONS_DIR = Path(__file__).parent / "definitions"

# File that collects comparison results for report generation
RESULTS_FILE = OUTPUT_DIR / "_comparison_results.json"


def _load_scenarios(filter_id: str | None = None) -> list[dict]:
    """Load all scenario definitions from YAML files."""
    scenarios = []
    for yml in sorted(DEFINITIONS_DIR.glob("*.yml")):
        data = yaml.safe_load(yml.read_text())
        for s in data.get("scenarios", []):
            if filter_id is None or s["id"] == filter_id:
                s["_source"] = yml.name
                scenarios.append(s)
    return scenarios


def _load_core_scenarios() -> list[dict]:
    """Load the core subset of scenarios tagged for comparison runs.

    Scenarios with ``comparison: true`` in their definition are included.
    This keeps CI run times manageable (~10 scenarios x 2 modes = ~20 invocations).
    """
    all_scenarios = _load_scenarios()
    core = [s for s in all_scenarios if s.get("comparison", False)]
    # Fallback: if nothing is tagged, use all scenarios
    return core if core else all_scenarios


def _load_canary_scenarios() -> list[dict]:
    """Load canary scenarios (tagged ``canary: true``).

    These are minimal, fast tests that verify the plugin context is loaded
    and actively affecting Claude's behavior.
    """
    all_scenarios = _load_scenarios()
    return [s for s in all_scenarios if s.get("canary", False)]


ALL_SCENARIOS = _load_scenarios()
CORE_SCENARIOS = _load_core_scenarios()
CANARY_SCENARIOS = _load_canary_scenarios()


def _skip_if_no_claude():
    if not shutil.which("claude"):
        pytest.skip("claude CLI not found on PATH")


def _save_comparison_result(result: dict):
    """Append a comparison result to the shared results file for report generation."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    if RESULTS_FILE.exists():
        try:
            results = json.loads(RESULTS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            results = []
    results.append(result)
    RESULTS_FILE.write_text(json.dumps(results, indent=2))


def _detect_skills_from_ndjson(scenario_id: str, label: str) -> list[str]:
    """Detect skill usage from saved NDJSON output."""
    ndjson_path = OUTPUT_DIR / scenario_id / f"{label}.ndjson"
    events = parse_ndjson(ndjson_path)
    return detect_skill_usage(events)


def _run_comparison(scenario: dict):
    """Run a scenario in both modes, evaluate, and save results for report."""
    config = scenario.get("config", {})
    kwargs = dict(
        scenario_id=scenario["id"],
        prompt=scenario["prompt"],
        max_turns=config.get("max_turns", 8),
        timeout_ms=config.get("timeout_ms", 120000),
    )

    result_with = run_scenario(**kwargs, with_plugin=True)
    result_without = run_scenario(**kwargs, with_plugin=False)

    eval_with = evaluate(result_with, scenario["expected"])
    eval_without = evaluate(result_without, scenario["expected"])
    comp = compare(eval_with, eval_without)

    # Detect skills from saved NDJSON output
    plugin_skills = _detect_skills_from_ndjson(scenario["id"], "with-plugin")
    baseline_skills = _detect_skills_from_ndjson(scenario["id"], "without-plugin")
    skill_differential = sorted(set(plugin_skills) - set(baseline_skills))

    print(f"\n{comp.summary()}")
    if plugin_skills:
        print(f"  Plugin skills detected: {', '.join(plugin_skills)}")
    if baseline_skills:
        print(f"  Baseline skills detected: {', '.join(baseline_skills)}")
    if skill_differential:
        print(f"  Skill differential (plugin-only): {', '.join(skill_differential)}")

    _save_comparison_result({
        "scenario_id": scenario["id"],
        "scenario_name": scenario.get("name", scenario["id"]),
        "prompt": scenario["prompt"],
        "source": scenario.get("_source", ""),
        "with_plugin": {
            "score": eval_with.score,
            "passed": eval_with.passed,
            "details": eval_with.details,
            "tool_call_count": len(result_with.tool_calls),
            "duration_ms": result_with.duration_ms,
            "tool_names": result_with.tool_names,
            "error": result_with.error,
            "skills_detected": plugin_skills,
        },
        "without_plugin": {
            "score": eval_without.score,
            "passed": eval_without.passed,
            "details": eval_without.details,
            "tool_call_count": len(result_without.tool_calls),
            "duration_ms": result_without.duration_ms,
            "tool_names": result_without.tool_names,
            "error": result_without.error,
            "skills_detected": baseline_skills,
        },
        "delta": comp.delta,
        "verdict": comp.verdict,
        "skill_differential": skill_differential,
        "expected_skills": scenario.get("expected_skills", []),
    })

    return comp, plugin_skills, baseline_skills


# ---------------------------------------------------------------------------
# Canary: verify the plugin-dir pipeline is actually loading and affecting
# behavior.  These run plugin-only and assert skill indicators appear.
# If canaries fail, the comparison suite results are meaningless.
# ---------------------------------------------------------------------------

@pytest.mark.canary
@pytest.mark.parametrize(
    "scenario",
    CANARY_SCENARIOS,
    ids=[s["id"] for s in CANARY_SCENARIOS],
)
def test_canary(scenario):
    """Verify plugin context is loaded and steering Claude's behavior.

    Runs the scenario with the plugin only (no baseline), then checks:
    1. The scenario passes the normal evaluation threshold.
    2. At least one expected skill is detected in the output.

    If canaries fail, the plugin is not being loaded properly and
    the comparison suite will not produce meaningful results.
    """
    _skip_if_no_claude()

    config = scenario.get("config", {})
    result = run_scenario(
        scenario_id=scenario["id"],
        prompt=scenario["prompt"],
        with_plugin=True,
        max_turns=config.get("max_turns", 6),
        timeout_ms=config.get("timeout_ms", 90000),
    )

    assert result.error is None, f"Runner error: {result.error}"

    eval_result = evaluate(result, scenario["expected"])
    print(f"\n{eval_result.summary()}")
    for k, v in eval_result.details.items():
        print(f"  {k}: {v}")

    assert eval_result.passed, (
        f"Canary failed evaluation: score {eval_result.score:.2f} — "
        f"plugin context may not be loaded. Details: {eval_result.details}"
    )

    # Check that expected skills were detected in the output
    expected_skills = scenario.get("expected_skills", [])
    if expected_skills:
        detected = _detect_skills_from_ndjson(scenario["id"], "with-plugin")
        print(f"  Expected skills: {expected_skills}")
        print(f"  Detected skills: {detected}")
        missing = set(expected_skills) - set(detected)
        assert not missing, (
            f"Canary skill detection failed: expected {expected_skills}, "
            f"detected {detected}, missing {sorted(missing)}. "
            f"Plugin context may not be steering behavior."
        )


# ---------------------------------------------------------------------------
# Primary test: always runs both plugin and MCP-only, compares side by side
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "scenario",
    ALL_SCENARIOS,
    ids=[s["id"] for s in ALL_SCENARIOS],
)
def test_scenario(scenario):
    """Run scenario with AND without plugin, compare results.

    This is the primary test mode. Every scenario is run twice:
    1. With plugin (skills, agents, commands loaded)
    2. Without plugin (MCP tools only -- the baseline)

    The plugin must not regress score by more than the regression threshold.
    When expected_skills are defined, the plugin run must show skill
    indicators that the baseline does not (skill differential).
    """
    _skip_if_no_claude()

    comp, plugin_skills, baseline_skills = _run_comparison(scenario)

    assert comp.delta >= REGRESSION_THRESHOLD, (
        f"Plugin regression: {comp.delta:+.2f} (threshold {REGRESSION_THRESHOLD})"
    )

    # Skill differential check: if the scenario declares expected_skills,
    # verify the plugin run detects at least one skill the baseline doesn't.
    expected_skills = scenario.get("expected_skills", [])
    if expected_skills:
        differential = set(plugin_skills) - set(baseline_skills)
        expected_set = set(expected_skills)
        overlap = differential & expected_set
        if not overlap:
            # Soft warning, not hard fail — LLM non-determinism means the
            # baseline might also stumble into skill-like patterns.
            pytest.xfail(
                f"Skill differential empty: expected plugin to show "
                f"{expected_skills} over baseline, but plugin={plugin_skills}, "
                f"baseline={baseline_skills}. Plugin may not be adding value "
                f"for this scenario."
            )


# ---------------------------------------------------------------------------
# Core subset: only scenarios tagged comparison: true in YAML (faster CI)
# ---------------------------------------------------------------------------

@pytest.mark.core
@pytest.mark.parametrize(
    "scenario",
    CORE_SCENARIOS,
    ids=[s["id"] for s in CORE_SCENARIOS],
)
def test_scenario_core(scenario):
    """Run core scenario subset with comparison (faster CI)."""
    _skip_if_no_claude()

    comp, plugin_skills, baseline_skills = _run_comparison(scenario)

    assert comp.delta >= REGRESSION_THRESHOLD, (
        f"Plugin regression: {comp.delta:+.2f} (threshold {REGRESSION_THRESHOLD})"
    )

    expected_skills = scenario.get("expected_skills", [])
    if expected_skills:
        differential = set(plugin_skills) - set(baseline_skills)
        expected_set = set(expected_skills)
        overlap = differential & expected_set
        if not overlap:
            pytest.xfail(
                f"Skill differential empty: expected plugin to show "
                f"{expected_skills} over baseline, but plugin={plugin_skills}, "
                f"baseline={baseline_skills}."
            )


# ---------------------------------------------------------------------------
# Plugin-only (no comparison baseline) -- useful for quick local validation
# ---------------------------------------------------------------------------

@pytest.mark.plugin_only
@pytest.mark.parametrize(
    "scenario",
    ALL_SCENARIOS,
    ids=[s["id"] for s in ALL_SCENARIOS],
)
def test_scenario_plugin_only(scenario):
    """Run scenario with plugin only (no baseline comparison)."""
    _skip_if_no_claude()

    config = scenario.get("config", {})
    result = run_scenario(
        scenario_id=scenario["id"],
        prompt=scenario["prompt"],
        with_plugin=True,
        max_turns=config.get("max_turns", 8),
        timeout_ms=config.get("timeout_ms", 120000),
    )

    assert result.error is None, f"Runner error: {result.error}"

    eval_result = evaluate(result, scenario["expected"])
    print(f"\n{eval_result.summary()}")
    for k, v in eval_result.details.items():
        print(f"  {k}: {v}")

    assert eval_result.passed, (
        f"Score {eval_result.score:.2f} below threshold: {eval_result.details}"
    )
