#!/usr/bin/env python3
"""Skill pressure test harness.

Runs scenarios against claude CLI with and without skill text to verify
that skills change the agent's reasoning in expected ways. No MCP tool
execution -- just testing whether the skill text changes reasoning.

Usage:
    python tests/skill-pressure/run.py                    # run all
    python tests/skill-pressure/run.py query-patterns     # run one skill's scenarios
    python tests/skill-pressure/run.py --skill-only       # skip baseline (faster)
    python tests/skill-pressure/run.py --model opus       # override model
"""

import argparse
import os
import sys
from pathlib import Path

import yaml

# Allow imports from this directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

from evaluator import check_patterns  # noqa: E402
from runner import run_without_skill, run_with_skill, REPO_ROOT, DEFAULT_MODEL  # noqa: E402

SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"


def load_scenarios(skill_filter: str | None = None) -> list[dict]:
    """Load scenario definitions from YAML files."""
    files = sorted(SCENARIOS_DIR.glob("*.yml"))
    if skill_filter:
        files = [f for f in files if f.stem == skill_filter]
        if not files:
            print(f"No scenario file found for skill: {skill_filter}")
            sys.exit(1)

    all_scenarios = []
    for f in files:
        data = yaml.safe_load(f.read_text())
        skill_file = REPO_ROOT / data["skill_file"]
        skill_content = skill_file.read_text()
        for scenario in data["scenarios"]:
            scenario["_skill_name"] = data["skill"]
            scenario["_skill_content"] = skill_content
        all_scenarios.extend(data["scenarios"])
    return all_scenarios


def run_all(
    skill_filter: str | None = None,
    skill_only: bool = False,
    model: str = DEFAULT_MODEL,
):
    """Run all scenarios and report results."""
    scenarios = load_scenarios(skill_filter)

    results = []
    total = len(scenarios)

    for i, scenario in enumerate(scenarios, 1):
        sid = scenario["id"]
        skill_name = scenario["_skill_name"]
        prompt = scenario["prompt"]
        skill_content = scenario["_skill_content"]

        print(f"\n{'='*60}")
        print(f"[{i}/{total}] {skill_name}/{sid}")
        print(f"{'='*60}")

        # --- Baseline (without skill) ---
        baseline_result = None
        if not skill_only:
            print("  Running baseline (without skill)...")
            try:
                baseline_text = run_without_skill(prompt, model=model)
                baseline_expected = scenario.get("without_skill", {}).get("expected_patterns", [])
                baseline_result = check_patterns(baseline_text, required=baseline_expected)
                if baseline_expected:
                    red_confirmed = baseline_result.passed
                    print(f"  Baseline: {'RED confirmed' if red_confirmed else 'RED not confirmed (baseline already passes)'}")
                else:
                    print("  Baseline: complete (no RED patterns to check)")
            except Exception as e:
                print(f"  Baseline ERROR: {e}")
                baseline_result = None

        # --- With skill ---
        print("  Running with skill...")
        skill_result = None
        try:
            skill_text = run_with_skill(prompt, skill_content, model=model)
            with_skill_cfg = scenario.get("with_skill", {})
            skill_result = check_patterns(
                skill_text,
                required=with_skill_cfg.get("required_patterns", []),
                anti=with_skill_cfg.get("anti_patterns", []),
            )
            print(f"  With skill: {skill_result.summary()}")
            if skill_result.missed_required:
                print(f"    Missing: {skill_result.missed_required}")
            if skill_result.violated_anti:
                print(f"    Violations: {skill_result.violated_anti}")
        except Exception as e:
            print(f"  With-skill ERROR: {e}")

        results.append({
            "id": sid,
            "skill": skill_name,
            "baseline": baseline_result,
            "with_skill": skill_result,
        })

    # --- Summary ---
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    passed = 0
    failed = 0
    errors = 0

    for r in results:
        sid = f"{r['skill']}/{r['id']}"
        sr = r["with_skill"]
        if sr is None:
            print(f"  ERROR  {sid}")
            errors += 1
        elif sr.passed:
            print(f"  PASS   {sid}")
            passed += 1
        else:
            print(f"  FAIL   {sid}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed, {errors} errors out of {len(results)} scenarios")

    if failed > 0 or errors > 0:
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Skill pressure test harness")
    parser.add_argument("skill", nargs="?", help="Run scenarios for a specific skill only")
    parser.add_argument("--skill-only", action="store_true", help="Skip baseline runs (faster)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model to use (default: {DEFAULT_MODEL})")
    args = parser.parse_args()

    # Allow env var override for model
    model = args.model
    if model == DEFAULT_MODEL:
        model = os.environ.get("SKILL_PRESSURE_MODEL", DEFAULT_MODEL)

    run_all(
        skill_filter=args.skill,
        skill_only=args.skill_only,
        model=model,
    )


if __name__ == "__main__":
    main()
