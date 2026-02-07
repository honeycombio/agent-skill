"""Pytest entry point for scenario tests.

Requires:
  - claude CLI installed and on PATH
  - Honeycomb MCP server configured (via .mcp.json or env)
  - ANTHROPIC_API_KEY set

Run: make test-scenarios
Comparison: make test-comparison
Single: make test-single ID=trigger-slow-endpoints
"""

import shutil
from pathlib import Path

import pytest
import yaml

from .comparator import compare, comparison_table, REGRESSION_THRESHOLD
from .evaluator import evaluate
from .runner import run_scenario

DEFINITIONS_DIR = Path(__file__).parent / "definitions"


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


ALL_SCENARIOS = _load_scenarios()


def _skip_if_no_claude():
    if not shutil.which("claude"):
        pytest.skip("claude CLI not found on PATH")


@pytest.mark.parametrize(
    "scenario",
    ALL_SCENARIOS,
    ids=[s["id"] for s in ALL_SCENARIOS],
)
def test_scenario_with_plugin(scenario):
    """Run scenario with plugin and evaluate."""
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


@pytest.mark.comparison
@pytest.mark.parametrize(
    "scenario",
    ALL_SCENARIOS,
    ids=[s["id"] for s in ALL_SCENARIOS],
)
def test_scenario_comparison(scenario):
    """Run scenario with and without plugin, compare results."""
    _skip_if_no_claude()

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

    print(f"\n{comp.summary()}")

    assert comp.delta >= REGRESSION_THRESHOLD, (
        f"Plugin regression: {comp.delta:+.2f} (threshold {REGRESSION_THRESHOLD})"
    )


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print comparison table if comparison tests were run."""
    # This hook is available but comparison table generation
    # is better handled by the CI workflow reading test output
    pass
