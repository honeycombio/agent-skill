"""Compare with-plugin vs without-plugin scenario results."""

from dataclasses import dataclass

from .evaluator import EvalResult


@dataclass
class ComparisonResult:
    """Comparison of with-plugin vs without-plugin for one scenario."""
    scenario_id: str
    with_score: float
    without_score: float
    delta: float
    verdict: str  # "improved", "regressed", "neutral"

    def summary(self) -> str:
        return (
            f"{self.scenario_id}: plugin={self.with_score:.2f} "
            f"baseline={self.without_score:.2f} "
            f"delta={self.delta:+.2f} ({self.verdict})"
        )


# Plugin should not make things worse by more than this
REGRESSION_THRESHOLD = -0.1


def compare(with_eval: EvalResult, without_eval: EvalResult) -> ComparisonResult:
    """Compare plugin vs no-plugin evaluation results."""
    delta = with_eval.score - without_eval.score

    if delta > 0.05:
        verdict = "improved"
    elif delta < REGRESSION_THRESHOLD:
        verdict = "regressed"
    else:
        verdict = "neutral"

    return ComparisonResult(
        scenario_id=with_eval.scenario_id,
        with_score=with_eval.score,
        without_score=without_eval.score,
        delta=delta,
        verdict=verdict,
    )


def comparison_table(results: list[ComparisonResult]) -> str:
    """Generate a markdown comparison table."""
    lines = [
        "| Scenario | With Plugin | Without | Delta | Verdict |",
        "|----------|------------|---------|-------|---------|",
    ]
    for r in results:
        lines.append(
            f"| {r.scenario_id} | {r.with_score:.2f} | "
            f"{r.without_score:.2f} | {r.delta:+.2f} | {r.verdict} |"
        )

    improved = sum(1 for r in results if r.verdict == "improved")
    regressed = sum(1 for r in results if r.verdict == "regressed")
    neutral = sum(1 for r in results if r.verdict == "neutral")
    lines.append("")
    lines.append(f"**Summary**: {improved} improved, {neutral} neutral, {regressed} regressed")

    return "\n".join(lines)
