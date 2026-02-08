"""Scenario runner — invokes claude CLI with/without plugin."""

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGIN_DIR = REPO_ROOT / "honeycomb"
MCP_CONFIG = REPO_ROOT / ".mcp.json"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

MCP_TOOLS = [
    "mcp__honeycomb__get_workspace_context",
    "mcp__honeycomb__get_environment",
    "mcp__honeycomb__get_dataset",
    "mcp__honeycomb__get_dataset_columns",
    "mcp__honeycomb__find_columns",
    "mcp__honeycomb__find_queries",
    "mcp__honeycomb__run_query",
    "mcp__honeycomb__get_query_results",
    "mcp__honeycomb__run_bubbleup",
    "mcp__honeycomb__get_trace",
    "mcp__honeycomb__get_service_map",
    "mcp__honeycomb__get_slos",
    "mcp__honeycomb__get_triggers",
    "mcp__honeycomb__feedback",
]

# Plugin tools that need to be allowed for skills/agents to activate.
# The Skill tool is how Claude Code invokes plugin skills — without it
# in --allowedTools, the plugin loads but skills can never fire.
PLUGIN_TOOLS = [
    "Skill",
    "Task",
]


@dataclass
class ToolCall:
    """A single tool invocation extracted from Claude output."""
    name: str
    arguments: dict = field(default_factory=dict)


@dataclass
class ScenarioResult:
    """Result of running a single scenario."""
    scenario_id: str
    with_plugin: bool
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_output: str = ""
    duration_ms: int = 0
    error: str | None = None

    @property
    def tool_names(self) -> list[str]:
        return [tc.name for tc in self.tool_calls]

    @property
    def raw_arguments(self) -> str:
        """All tool call arguments as a single string for pattern matching."""
        return json.dumps([tc.arguments for tc in self.tool_calls])


def _strip_mcp_prefix(name: str) -> str:
    """Strip mcp__honeycomb__ prefix from tool names."""
    prefix = "mcp__honeycomb__"
    return name[len(prefix):] if name.startswith(prefix) else name


def _extract_tool_calls_from_ndjson(stdout: str) -> list[ToolCall]:
    """Extract tool calls from stream-json (NDJSON) output.

    Each line is a JSON object. We look for assistant messages containing
    tool_use content blocks.
    """
    calls = []
    for line in stdout.strip().splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        # assistant message events contain the content blocks
        if event.get("type") == "assistant":
            msg = event.get("message", {})
            for block in msg.get("content", []):
                if block.get("type") == "tool_use":
                    calls.append(ToolCall(
                        name=_strip_mcp_prefix(block.get("name", "")),
                        arguments=block.get("input", {}),
                    ))
    return calls


def _save_output(scenario_id: str, with_plugin: bool, stdout: str, stderr: str):
    """Save raw output to flat files for inspection."""
    label = "with-plugin" if with_plugin else "without-plugin"
    out_dir = OUTPUT_DIR / scenario_id
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / f"{label}.ndjson").write_text(stdout)
    if stderr:
        (out_dir / f"{label}.stderr").write_text(stderr)


def run_scenario(
    scenario_id: str,
    prompt: str,
    with_plugin: bool = True,
    max_turns: int = 8,
    timeout_ms: int = 120000,
) -> ScenarioResult:
    """Run a prompt through claude CLI and collect tool calls.

    Uses --output-format stream-json --verbose to get per-message output
    including tool_use blocks. All output is saved to tests/scenarios/output/.
    """
    allowed = list(MCP_TOOLS)
    if with_plugin:
        allowed.extend(PLUGIN_TOOLS)

    cmd = [
        "claude", "-p", prompt,
        "--output-format", "stream-json",
        "--verbose",
        "--max-turns", str(max_turns),
        "--allowedTools", ",".join(allowed),
    ]
    if MCP_CONFIG.exists():
        cmd.extend(["--mcp-config", str(MCP_CONFIG)])
    if with_plugin:
        cmd.extend(["--plugin-dir", str(PLUGIN_DIR)])

    env = {**os.environ}

    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_ms / 1000,
            cwd=str(REPO_ROOT),
            env=env,
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        _save_output(scenario_id, with_plugin, proc.stdout, proc.stderr)

        if proc.returncode != 0:
            return ScenarioResult(
                scenario_id=scenario_id,
                with_plugin=with_plugin,
                raw_output=proc.stderr or proc.stdout,
                duration_ms=duration_ms,
                error=f"claude exited with code {proc.returncode}: {proc.stderr[:500]}",
            )

        tool_calls = _extract_tool_calls_from_ndjson(proc.stdout)

        return ScenarioResult(
            scenario_id=scenario_id,
            with_plugin=with_plugin,
            tool_calls=tool_calls,
            raw_output=proc.stdout,
            duration_ms=duration_ms,
        )

    except subprocess.TimeoutExpired:
        duration_ms = int((time.monotonic() - start) * 1000)
        return ScenarioResult(
            scenario_id=scenario_id,
            with_plugin=with_plugin,
            duration_ms=duration_ms,
            error=f"Timed out after {timeout_ms}ms",
        )
