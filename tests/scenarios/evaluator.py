"""Score scenario results against expected patterns."""

import re
from dataclasses import dataclass

from .runner import ScenarioResult


@dataclass
class EvalResult:
    """Evaluation of a single scenario run."""
    scenario_id: str
    score: float
    passed: bool
    details: dict

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] {self.scenario_id}: {self.score:.2f}"


# Scoring weights
WEIGHT_REQUIRED_TOOLS = 0.30
WEIGHT_REQUIRED_PATTERNS = 0.25
WEIGHT_ANTI_PATTERNS = 0.20
WEIGHT_TOOL_ORDERING = 0.15
WEIGHT_RECOMMENDED_TOOLS = 0.10

PASS_THRESHOLD = 0.6


def evaluate(
    result: ScenarioResult,
    expected: dict,
    pass_threshold: float = PASS_THRESHOLD,
) -> EvalResult:
    """Score a scenario result against expectations.

    Args:
        result: The scenario run result.
        expected: The 'expected' dict from the scenario YAML.
        pass_threshold: Minimum score to pass.
    """
    if result.error:
        return EvalResult(
            scenario_id=result.scenario_id,
            score=0.0,
            passed=False,
            details={"error": result.error},
        )

    details = {}
    tool_names = result.tool_names

    # Required tools (30%)
    required = expected.get("required_tools", [])
    if required:
        found = [t for t in required if t in tool_names]
        ratio = len(found) / len(required)
        details["required_tools"] = {"found": found, "missing": [t for t in required if t not in tool_names], "ratio": ratio}
    else:
        ratio = 1.0
        details["required_tools"] = {"found": [], "missing": [], "ratio": 1.0}
    score_required = ratio * WEIGHT_REQUIRED_TOOLS

    # Required patterns (25%)
    patterns = expected.get("required_patterns", [])
    # Search tool call arguments only (not raw output which includes system noise)
    search_text = result.raw_arguments
    if patterns:
        matched = [p for p in patterns if re.search(p, search_text)]
        ratio = len(matched) / len(patterns)
        details["required_patterns"] = {"matched": matched, "missed": [p for p in patterns if p not in matched], "ratio": ratio}
    else:
        ratio = 1.0
        details["required_patterns"] = {"matched": [], "missed": [], "ratio": 1.0}
    score_patterns = ratio * WEIGHT_REQUIRED_PATTERNS

    # Anti-patterns (20%) — score 1.0 if none found, 0.0 for each found
    # Check against tool names and arguments (not raw output noise)
    anti_search_text = " ".join(tool_names) + " " + result.raw_arguments
    anti = expected.get("anti_patterns", [])
    if anti:
        violations = [p for p in anti if re.search(p, anti_search_text)]
        ratio = 1.0 - (len(violations) / len(anti))
        details["anti_patterns"] = {"violations": violations, "ratio": ratio}
    else:
        ratio = 1.0
        details["anti_patterns"] = {"violations": [], "ratio": 1.0}
    score_anti = ratio * WEIGHT_ANTI_PATTERNS

    # Tool ordering (15%)
    orderings = expected.get("tool_ordering", [])
    if orderings:
        correct = 0
        for order in orderings:
            if _check_order(tool_names, order):
                correct += 1
        ratio = correct / len(orderings)
        details["tool_ordering"] = {"correct": correct, "total": len(orderings), "ratio": ratio}
    else:
        ratio = 1.0
        details["tool_ordering"] = {"correct": 0, "total": 0, "ratio": 1.0}
    score_ordering = ratio * WEIGHT_TOOL_ORDERING

    # Recommended tools (10%)
    recommended = expected.get("recommended_tools", [])
    if recommended:
        found = [t for t in recommended if t in tool_names]
        ratio = len(found) / len(recommended)
        details["recommended_tools"] = {"found": found, "missing": [t for t in recommended if t not in found], "ratio": ratio}
    else:
        ratio = 1.0
        details["recommended_tools"] = {"found": [], "missing": [], "ratio": 1.0}
    score_recommended = ratio * WEIGHT_RECOMMENDED_TOOLS

    total = score_required + score_patterns + score_anti + score_ordering + score_recommended
    details["total_score"] = total

    return EvalResult(
        scenario_id=result.scenario_id,
        score=total,
        passed=total >= pass_threshold,
        details=details,
    )


def _check_order(tool_names: list[str], order: list[str]) -> bool:
    """Check that tools appear in the specified order (not necessarily adjacent)."""
    last_idx = -1
    for tool in order:
        try:
            idx = tool_names.index(tool, last_idx + 1)
            last_idx = idx
        except ValueError:
            return False
    return True
