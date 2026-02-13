"""Skill pressure test runner -- invokes claude CLI with/without skill text."""

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MCP_CONFIG = REPO_ROOT / ".mcp.json"
DEFAULT_MODEL = "sonnet"

# Appended to every prompt so the agent describes its approach in text
# rather than trying to call tools (which would consume the single turn).
REASONING_SUFFIX = "\n\nDescribe your reasoning and what you would do. Do not call any tools."


def run_without_skill(prompt: str, model: str = DEFAULT_MODEL) -> str:
    """Run a prompt through claude CLI without any skill text."""
    return _run(prompt, model=model)


def run_with_skill(prompt: str, skill_content: str, model: str = DEFAULT_MODEL) -> str:
    """Run a prompt through claude CLI with skill text appended to system prompt."""
    return _run(prompt, skill_content=skill_content, model=model)


def _run(prompt: str, skill_content: str | None = None, model: str = DEFAULT_MODEL) -> str:
    """Core runner: invoke claude -p with common flags."""
    cmd = [
        "claude", "-p", prompt + REASONING_SUFFIX,
        "--max-turns", "1",
        "--output-format", "text",
        "--no-session-persistence",
        "--model", model,
    ]
    if MCP_CONFIG.exists():
        cmd.extend(["--mcp-config", str(MCP_CONFIG)])
    if skill_content:
        cmd.extend(["--append-system-prompt", skill_content])

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(REPO_ROOT),
        env={**os.environ},
    )

    if proc.returncode != 0:
        raise RuntimeError(
            f"claude exited with code {proc.returncode}: {proc.stderr[:500]}"
        )

    return proc.stdout
