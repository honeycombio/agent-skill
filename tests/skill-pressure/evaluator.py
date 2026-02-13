"""Pattern-based evaluation for skill pressure tests."""

import re
from dataclasses import dataclass, field


@dataclass
class EvalResult:
    """Result of evaluating a response against expected patterns."""
    passed: bool
    matched_required: list[str] = field(default_factory=list)
    missed_required: list[str] = field(default_factory=list)
    violated_anti: list[str] = field(default_factory=list)
    raw_text: str = ""

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        parts = [f"[{status}]"]
        if self.missed_required:
            parts.append(f"missing: {self.missed_required}")
        if self.violated_anti:
            parts.append(f"violations: {self.violated_anti}")
        return " ".join(parts)


def check_patterns(
    text: str,
    required: list[str] | None = None,
    anti: list[str] | None = None,
) -> EvalResult:
    """Check text against required and anti patterns.

    Args:
        text: Response text to evaluate.
        required: Regex patterns that must appear.
        anti: Regex patterns that must NOT appear.

    Returns:
        EvalResult with pass/fail and details.
    """
    required = required or []
    anti = anti or []

    matched_required = [p for p in required if re.search(p, text, re.IGNORECASE)]
    missed_required = [p for p in required if not re.search(p, text, re.IGNORECASE)]
    violated_anti = [p for p in anti if re.search(p, text, re.IGNORECASE)]

    passed = len(missed_required) == 0 and len(violated_anti) == 0

    return EvalResult(
        passed=passed,
        matched_required=matched_required,
        missed_required=missed_required,
        violated_anti=violated_anti,
        raw_text=text,
    )
