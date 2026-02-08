"""Generate a self-contained HTML comparison report from scenario test output.

Reads NDJSON output files saved by the runner and comparison results saved by
the test harness, then produces a single HTML file with:
  - Summary dashboard (scores, verdicts, overall stats)
  - Per-scenario side-by-side timeline (plugin vs MCP-only)
  - Collapsible tool call details with arguments and results
  - Evaluation scoring breakdown
  - Tool call counts and wall clock time per scenario
  - Skill usage detection and indicators
  - Full markdown rendering in text blocks (no truncation)

Usage:
    python -m tests.scenarios.report                     # default paths
    python -m tests.scenarios.report --output report.html
"""

import html
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
DEFAULT_REPORT_PATH = OUTPUT_DIR / "comparison-report.html"


# ---------------------------------------------------------------------------
# NDJSON timeline parsing
# ---------------------------------------------------------------------------

@dataclass
class TimelineEvent:
    """A single event in the scenario execution timeline."""
    event_type: str  # "text", "tool_call", "tool_result", "error"
    content: str = ""
    tool_name: str = ""
    tool_args: dict = field(default_factory=dict)


def _strip_mcp_prefix(name: str) -> str:
    prefix = "mcp__honeycomb__"
    return name[len(prefix):] if name.startswith(prefix) else name


# Known skill names from the plugin
SKILL_NAMES = [
    "query-patterns",
    "production-investigation",
    "slos-and-triggers",
    "otel-instrumentation",
    "beeline-migration",
]


def detect_skill_usage(events: list["TimelineEvent"]) -> list[str]:
    """Detect which skills appear to be in use based on timeline events.

    Skills are context-based (not tool_use blocks), so we infer usage from:
    1. Explicit Skill tool_use blocks (if present)
    2. Text referencing skill concepts or names
    3. Tool call patterns that match skill-guided behavior
    """
    detected: set[str] = set()

    # Patterns that indicate specific skill guidance is active
    skill_indicators = {
        "query-patterns": [
            r"HEATMAP",
            r"P(?:99|95|90|50|75)\b",
            r"relational\s+field",
            r"GROUP\s*BY",
            r"VISUALIZE",
            r"query.patterns",
        ],
        "production-investigation": [
            r"BubbleUp",
            r"investigation\s+playbook",
            r"root\s+cause\s+analysis",
            r"trace\s+exploration",
            r"production.investigation",
        ],
        "slos-and-triggers": [
            r"SLO\b",
            r"burn\s+rate",
            r"error\s+budget",
            r"service\s+level",
            r"slos.and.triggers",
        ],
        "otel-instrumentation": [
            r"OpenTelemetry",
            r"OTEL\b",
            r"otel.instrumentation",
            r"collector\s+config",
        ],
        "beeline-migration": [
            r"Beeline",
            r"beeline.migration",
            r"W3C\s+propagation",
        ],
    }

    # Collect all text from events
    all_text = []
    for ev in events:
        if ev.event_type == "text":
            all_text.append(ev.content)
        elif ev.event_type == "tool_call":
            all_text.append(json.dumps(ev.tool_args))
            # Check for explicit Skill tool invocation
            if ev.tool_name.lower() == "skill":
                skill_arg = ev.tool_args.get("skill", "")
                if skill_arg:
                    detected.add(skill_arg)

    combined = " ".join(all_text)
    for skill_name, patterns in skill_indicators.items():
        for pattern in patterns:
            if re.search(pattern, combined, re.IGNORECASE):
                detected.add(skill_name)
                break

    return sorted(detected)


def _markdown_to_html(text: str) -> str:
    """Convert markdown text to HTML. Handles common markdown constructs.

    This is a lightweight converter for rendering Claude's text output.
    Handles: headers, bold, italic, code blocks, inline code, links, lists,
    blockquotes, horizontal rules, and paragraphs.
    """
    # Escape HTML first, then selectively convert markdown
    text = html.escape(text)

    # Fenced code blocks (```lang ... ```)
    def _code_block(m: re.Match) -> str:
        lang = m.group(1) or ""
        code = m.group(2)
        lang_attr = f' class="language-{lang}"' if lang else ""
        return f'<pre class="md-code-block"><code{lang_attr}>{code}</code></pre>'
    text = re.sub(r"```(\w*)\n(.*?)```", _code_block, text, flags=re.DOTALL)

    # Inline code
    text = re.sub(r"`([^`\n]+)`", r'<code class="md-inline-code">\1</code>', text)

    # Headers (## ... )
    text = re.sub(r"^######\s+(.+)$", r"<h6>\1</h6>", text, flags=re.MULTILINE)
    text = re.sub(r"^#####\s+(.+)$", r"<h5>\1</h5>", text, flags=re.MULTILINE)
    text = re.sub(r"^####\s+(.+)$", r"<h4>\1</h4>", text, flags=re.MULTILINE)
    text = re.sub(r"^###\s+(.+)$", r"<h3>\1</h3>", text, flags=re.MULTILINE)
    text = re.sub(r"^##\s+(.+)$", r"<h2>\1</h2>", text, flags=re.MULTILINE)
    text = re.sub(r"^#\s+(.+)$", r"<h1>\1</h1>", text, flags=re.MULTILINE)

    # Bold and italic
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)

    # Links [text](url)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        r'<a href="\2" target="_blank" rel="noopener">\1</a>',
        text,
    )

    # Unordered list items (- item or * item)
    text = re.sub(r"^[\-\*]\s+(.+)$", r"<li>\1</li>", text, flags=re.MULTILINE)
    # Wrap consecutive <li> tags in <ul>
    text = re.sub(
        r"((?:<li>.*?</li>\n?)+)",
        r"<ul>\1</ul>",
        text,
    )

    # Ordered list items (1. item)
    text = re.sub(r"^\d+\.\s+(.+)$", r"<li>\1</li>", text, flags=re.MULTILINE)

    # Blockquotes
    text = re.sub(
        r"^&gt;\s+(.+)$",
        r"<blockquote>\1</blockquote>",
        text,
        flags=re.MULTILINE,
    )

    # Horizontal rules
    text = re.sub(r"^---+$", r"<hr>", text, flags=re.MULTILINE)

    # Paragraphs: convert double newlines to paragraph breaks
    text = re.sub(r"\n\n+", r"</p><p>", text)
    # Single newlines to <br> (within paragraphs)
    text = re.sub(r"\n", r"<br>", text)

    # Wrap in paragraph tags if not already wrapped in block elements
    if not text.startswith(("<h", "<pre", "<ul", "<ol", "<blockquote", "<hr")):
        text = f"<p>{text}</p>"

    return text


def _format_duration(ms: int) -> str:
    """Format milliseconds as human-readable duration."""
    if ms < 1000:
        return f"{ms}ms"
    secs = ms / 1000
    if secs < 60:
        return f"{secs:.1f}s"
    mins = int(secs // 60)
    remaining_secs = secs % 60
    return f"{mins}m {remaining_secs:.0f}s"


def parse_ndjson(path: Path) -> list[TimelineEvent]:
    """Parse NDJSON output into a timeline of events."""
    events: list[TimelineEvent] = []
    if not path.exists():
        return events

    for line in path.read_text().strip().splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        event_type = event.get("type", "")

        if event_type == "assistant":
            msg = event.get("message", {})
            for block in msg.get("content", []):
                block_type = block.get("type", "")
                if block_type == "text":
                    text = block.get("text", "").strip()
                    if text:
                        events.append(TimelineEvent(
                            event_type="text",
                            content=text,
                        ))
                elif block_type == "tool_use":
                    events.append(TimelineEvent(
                        event_type="tool_call",
                        tool_name=_strip_mcp_prefix(block.get("name", "")),
                        tool_args=block.get("input", {}),
                    ))

        elif event_type == "result":
            # Final result message from Claude
            msg = event.get("message", event)
            content_blocks = msg.get("content", [])
            if isinstance(content_blocks, str):
                events.append(TimelineEvent(
                    event_type="text",
                    content=content_blocks,
                ))
            elif isinstance(content_blocks, list):
                for block in content_blocks:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "").strip()
                        if text:
                            events.append(TimelineEvent(
                                event_type="text",
                                content=text,
                            ))

        elif event_type == "user":
            # User messages carry tool results
            msg = event.get("message", {})
            for block in msg.get("content", []):
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    result_content = block.get("content", "")
                    if isinstance(result_content, list):
                        parts = []
                        for part in result_content:
                            if isinstance(part, dict):
                                parts.append(part.get("text", json.dumps(part)))
                            else:
                                parts.append(str(part))
                        result_content = "\n".join(parts)
                    events.append(TimelineEvent(
                        event_type="tool_result",
                        content=str(result_content),
                    ))

    return events


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def _escape(text: str) -> str:
    """HTML-escape text."""
    return html.escape(str(text))


def _format_json(obj: dict | list | str) -> str:
    """Pretty-print JSON."""
    if isinstance(obj, str):
        return obj
    return json.dumps(obj, indent=2)


def _verdict_class(verdict: str) -> str:
    """CSS class for verdict."""
    return {"improved": "verdict-improved", "regressed": "verdict-regressed"}.get(
        verdict, "verdict-neutral"
    )


def _score_bar(score: float) -> str:
    """Inline HTML for a score bar."""
    pct = max(0, min(100, score * 100))
    color = "#22c55e" if score >= 0.6 else "#f59e0b" if score >= 0.4 else "#ef4444"
    return (
        f'<div class="score-bar">'
        f'<div class="score-fill" style="width:{pct:.0f}%;background:{color}"></div>'
        f'<span class="score-label">{score:.2f}</span>'
        f'</div>'
    )


def _render_timeline(events: list[TimelineEvent], side_id: str) -> str:
    """Render a timeline of events as HTML.

    Text blocks are rendered as parsed markdown. Tool arguments and results
    are shown in full (no truncation) with scrollable containers.
    """
    if not events:
        return '<div class="timeline-empty">No output recorded</div>'

    parts = []
    step = 0
    for ev in events:
        step += 1
        uid = f"{side_id}-step-{step}"

        if ev.event_type == "text":
            rendered = _markdown_to_html(ev.content)
            parts.append(
                f'<div class="tl-event tl-text">'
                f'<div class="tl-badge">Text</div>'
                f'<div class="tl-body md-rendered">{rendered}</div>'
                f'</div>'
            )

        elif ev.event_type == "tool_call":
            args_json = _format_json(ev.tool_args)
            parts.append(
                f'<div class="tl-event tl-tool-call">'
                f'<div class="tl-badge tl-badge-tool">{_escape(ev.tool_name)}</div>'
                f'<details id="{uid}">'
                f'<summary>Arguments</summary>'
                f'<pre class="tl-code">{_escape(args_json)}</pre>'
                f'</details>'
                f'</div>'
            )

        elif ev.event_type == "tool_result":
            parts.append(
                f'<div class="tl-event tl-tool-result">'
                f'<div class="tl-badge tl-badge-result">Result</div>'
                f'<details id="{uid}">'
                f'<summary>Tool response</summary>'
                f'<pre class="tl-code">{_escape(ev.content)}</pre>'
                f'</details>'
                f'</div>'
            )

    return "\n".join(parts)


def _render_eval_details(details: dict) -> str:
    """Render evaluation scoring breakdown."""
    parts = ['<div class="eval-details">']

    for key in ["required_tools", "required_patterns", "anti_patterns",
                "tool_ordering", "recommended_tools"]:
        info = details.get(key, {})
        if not isinstance(info, dict):
            continue
        ratio = info.get("ratio", 0)
        pct = ratio * 100

        detail_items = []
        if "found" in info and info["found"]:
            detail_items.append(f'Found: {", ".join(info["found"])}')
        if "missing" in info and info["missing"]:
            detail_items.append(f'Missing: {", ".join(info["missing"])}')
        if "matched" in info and info["matched"]:
            detail_items.append(f'Matched: {", ".join(info["matched"])}')
        if "missed" in info and info["missed"]:
            detail_items.append(f'Missed: {", ".join(info["missed"])}')
        if "violations" in info and info["violations"]:
            detail_items.append(f'Violations: {", ".join(info["violations"])}')
        if "correct" in info:
            detail_items.append(f'{info["correct"]}/{info.get("total", 0)} correct')

        label = key.replace("_", " ").title()
        detail_str = " | ".join(detail_items) if detail_items else ""

        color = "#22c55e" if ratio >= 0.8 else "#f59e0b" if ratio >= 0.5 else "#ef4444"
        parts.append(
            f'<div class="eval-row">'
            f'<span class="eval-label">{_escape(label)}</span>'
            f'<span class="eval-ratio" style="color:{color}">{pct:.0f}%</span>'
            f'<span class="eval-detail">{_escape(detail_str)}</span>'
            f'</div>'
        )

    parts.append('</div>')
    return "\n".join(parts)


def _render_skill_badges(skills: list[str]) -> str:
    """Render skill usage badges."""
    if not skills:
        return '<span class="skill-none">No skills detected</span>'
    return " ".join(
        f'<span class="skill-badge">{_escape(s)}</span>' for s in skills
    )


def _render_scenario_section(result: dict, output_dir: Path) -> str:
    """Render a single scenario comparison section."""
    sid = result["scenario_id"]
    name = result.get("scenario_name", sid)
    prompt = result.get("prompt", "")
    verdict = result.get("verdict", "neutral")
    delta = result.get("delta", 0)

    with_data = result["with_plugin"]
    without_data = result["without_plugin"]
    with_score = with_data["score"]
    without_score = without_data["score"]

    # Tool call counts and durations (from enriched results)
    with_tc = with_data.get("tool_call_count", 0)
    without_tc = without_data.get("tool_call_count", 0)
    with_dur = with_data.get("duration_ms", 0)
    without_dur = without_data.get("duration_ms", 0)

    # Load NDJSON timelines
    scenario_dir = output_dir / sid
    plugin_events = parse_ndjson(scenario_dir / "with-plugin.ndjson")
    baseline_events = parse_ndjson(scenario_dir / "without-plugin.ndjson")

    # If tool_call_count is missing from results, count from NDJSON
    if with_tc == 0 and plugin_events:
        with_tc = sum(1 for e in plugin_events if e.event_type == "tool_call")
    if without_tc == 0 and baseline_events:
        without_tc = sum(1 for e in baseline_events if e.event_type == "tool_call")

    # Skill usage: prefer saved results, fall back to re-detecting from NDJSON
    plugin_skills = with_data.get("skills_detected") or detect_skill_usage(plugin_events)
    baseline_skills = without_data.get("skills_detected") or detect_skill_usage(baseline_events)
    skill_differential = result.get("skill_differential", sorted(set(plugin_skills) - set(baseline_skills)))
    expected_skills = result.get("expected_skills", [])

    verdict_label = verdict.upper()
    delta_sign = "+" if delta > 0 else ""

    # Format duration strings
    with_dur_str = _format_duration(with_dur) if with_dur > 0 else "N/A"
    without_dur_str = _format_duration(without_dur) if without_dur > 0 else "N/A"

    return f"""
    <div class="scenario" id="scenario-{_escape(sid)}" data-verdict="{_escape(verdict)}">
      <div class="scenario-header" onclick="toggleScenario('{_escape(sid)}')">
        <div class="scenario-title">
          <span class="scenario-toggle" id="toggle-{_escape(sid)}">&#9654;</span>
          <h3>{_escape(name)}</h3>
          <span class="badge {_verdict_class(verdict)}">{verdict_label} ({delta_sign}{delta:.2f})</span>
        </div>
        <div class="scenario-scores">
          <span class="score-chip">Plugin: {with_score:.2f}</span>
          <span class="score-chip">Baseline: {without_score:.2f}</span>
        </div>
      </div>

      <div class="scenario-body" id="body-{_escape(sid)}" style="display:none">
        <div class="prompt-section">
          <strong>Prompt:</strong> {_escape(prompt)}
        </div>

        <div class="scenario-metrics">
          <div class="metric-group">
            <h5>Tool Calls</h5>
            <div class="metric-compare">
              <span class="metric-val">Plugin: <strong>{with_tc}</strong></span>
              <span class="metric-val">Baseline: <strong>{without_tc}</strong></span>
              <span class="metric-delta {"metric-better" if with_tc <= without_tc else "metric-worse"}">\
{("+" if with_tc - without_tc > 0 else "")}{with_tc - without_tc}</span>
            </div>
          </div>
          <div class="metric-group">
            <h5>Wall Clock Time</h5>
            <div class="metric-compare">
              <span class="metric-val">Plugin: <strong>{with_dur_str}</strong></span>
              <span class="metric-val">Baseline: <strong>{without_dur_str}</strong></span>
            </div>
          </div>
          <div class="metric-group">
            <h5>Skills Detected (Plugin)</h5>
            <div class="metric-compare">
              {_render_skill_badges(plugin_skills)}
            </div>
          </div>
          <div class="metric-group">
            <h5>Skills Detected (Baseline)</h5>
            <div class="metric-compare">
              {_render_skill_badges(baseline_skills)}
            </div>
          </div>
          <div class="metric-group">
            <h5>Skill Differential</h5>
            <div class="metric-compare">
              {_render_skill_badges(skill_differential) if skill_differential else '<span class="skill-none">None — plugin not adding unique skill behavior</span>'}
            </div>
          </div>
          <div class="metric-group">
            <h5>Expected Skills</h5>
            <div class="metric-compare">
              {_render_skill_badges(expected_skills) if expected_skills else '<span class="skill-none">Not specified</span>'}
            </div>
          </div>
        </div>

        <div class="comparison-grid">
          <div class="comparison-col">
            <h4>With Plugin {_score_bar(with_score)}</h4>
            {_render_eval_details(with_data.get("details", {}))}
            <div class="timeline">
              {_render_timeline(plugin_events, f"{sid}-plugin")}
            </div>
          </div>
          <div class="comparison-col">
            <h4>MCP Only (Baseline) {_score_bar(without_score)}</h4>
            {_render_eval_details(without_data.get("details", {}))}
            <div class="timeline">
              {_render_timeline(baseline_events, f"{sid}-baseline")}
            </div>
          </div>
        </div>
      </div>
    </div>"""


def generate_report(
    output_dir: Path = OUTPUT_DIR,
    report_path: Path | None = None,
) -> Path:
    """Generate the full HTML comparison report."""
    if report_path is None:
        report_path = DEFAULT_REPORT_PATH

    results_file = output_dir / "_comparison_results.json"
    if not results_file.exists():
        print(f"No comparison results found at {results_file}", file=sys.stderr)
        print("Run tests first: make test-scenarios", file=sys.stderr)
        sys.exit(1)

    results = json.loads(results_file.read_text())
    if not results:
        print("Comparison results file is empty", file=sys.stderr)
        sys.exit(1)

    # Compute summary stats
    total = len(results)
    improved = sum(1 for r in results if r.get("verdict") == "improved")
    regressed = sum(1 for r in results if r.get("verdict") == "regressed")
    neutral = total - improved - regressed
    avg_plugin = sum(r["with_plugin"]["score"] for r in results) / total if total else 0
    avg_baseline = sum(r["without_plugin"]["score"] for r in results) / total if total else 0
    avg_delta = avg_plugin - avg_baseline

    # Tool call and duration stats
    total_plugin_calls = sum(r["with_plugin"].get("tool_call_count", 0) for r in results)
    total_baseline_calls = sum(r["without_plugin"].get("tool_call_count", 0) for r in results)
    avg_plugin_calls = total_plugin_calls / total if total else 0
    avg_baseline_calls = total_baseline_calls / total if total else 0
    total_plugin_dur = sum(r["with_plugin"].get("duration_ms", 0) for r in results)
    total_baseline_dur = sum(r["without_plugin"].get("duration_ms", 0) for r in results)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Render scenario sections
    scenario_sections = "\n".join(
        _render_scenario_section(r, output_dir) for r in results
    )

    # Summary table rows
    summary_rows = ""
    for r in results:
        sid = r["scenario_id"]
        v = r.get("verdict", "neutral")
        d = r.get("delta", 0)
        ds = "+" if d > 0 else ""
        ws = r["with_plugin"]["score"]
        bs = r["without_plugin"]["score"]
        wtc = r["with_plugin"].get("tool_call_count", 0)
        btc = r["without_plugin"].get("tool_call_count", 0)
        wdur = r["with_plugin"].get("duration_ms", 0)
        bdur = r["without_plugin"].get("duration_ms", 0)
        wdur_str = _format_duration(wdur) if wdur > 0 else "N/A"
        bdur_str = _format_duration(bdur) if bdur > 0 else "N/A"
        summary_rows += (
            f'<tr class="summary-row" onclick="scrollToScenario(\'{_escape(sid)}\')">'
            f'<td><a href="#scenario-{_escape(sid)}">{_escape(sid)}</a></td>'
            f'<td>{ws:.2f}</td>'
            f'<td>{bs:.2f}</td>'
            f'<td class="{_verdict_class(v)}">{ds}{d:.2f}</td>'
            f'<td>{wtc}</td>'
            f'<td>{btc}</td>'
            f'<td>{wdur_str}</td>'
            f'<td>{bdur_str}</td>'
            f'<td><span class="badge {_verdict_class(v)}">{v.upper()}</span></td>'
            f'</tr>'
        )

    report_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Honeycomb Plugin - Scenario Comparison Report</title>
<style>
  :root {{
    --bg: #0d1117;
    --surface: #161b22;
    --surface-2: #1c2129;
    --border: #30363d;
    --text: #e6edf3;
    --text-muted: #8b949e;
    --accent: #58a6ff;
    --green: #3fb950;
    --red: #f85149;
    --yellow: #d29922;
    --orange: #db6d28;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 2rem;
    max-width: 1400px;
    margin: 0 auto;
  }}

  h1 {{ font-size: 1.8rem; margin-bottom: 0.5rem; }}
  h2 {{ font-size: 1.3rem; margin-bottom: 1rem; color: var(--text-muted); }}
  h3 {{ font-size: 1.1rem; margin: 0; display: inline; }}
  h4 {{ font-size: 0.95rem; margin-bottom: 0.5rem; color: var(--text-muted); }}

  .header {{
    border-bottom: 1px solid var(--border);
    padding-bottom: 1.5rem;
    margin-bottom: 2rem;
  }}
  .header p {{ color: var(--text-muted); font-size: 0.9rem; }}

  /* Stats cards */
  .stats {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
  }}
  .stat-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem 1.25rem;
  }}
  .stat-card .stat-value {{
    font-size: 1.8rem;
    font-weight: 700;
    display: block;
  }}
  .stat-card .stat-label {{
    font-size: 0.8rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}

  /* Summary table */
  .summary-table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 2rem;
    background: var(--surface);
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid var(--border);
  }}
  .summary-table th {{
    background: var(--surface-2);
    padding: 0.75rem 1rem;
    text-align: left;
    font-size: 0.85rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.03em;
    border-bottom: 1px solid var(--border);
  }}
  .summary-table td {{
    padding: 0.6rem 1rem;
    border-bottom: 1px solid var(--border);
    font-size: 0.9rem;
  }}
  .summary-row {{ cursor: pointer; }}
  .summary-row:hover {{ background: var(--surface-2); }}
  .summary-table a {{ color: var(--accent); text-decoration: none; }}
  .summary-table a:hover {{ text-decoration: underline; }}

  /* Badges */
  .badge {{
    display: inline-block;
    padding: 0.15rem 0.6rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }}
  .verdict-improved {{ background: rgba(63, 185, 80, 0.15); color: var(--green); }}
  .verdict-regressed {{ background: rgba(248, 81, 73, 0.15); color: var(--red); }}
  .verdict-neutral {{ background: rgba(139, 148, 158, 0.15); color: var(--text-muted); }}

  /* Score bar */
  .score-bar {{
    display: inline-flex;
    align-items: center;
    width: 120px;
    height: 18px;
    background: var(--surface-2);
    border-radius: 9px;
    overflow: hidden;
    position: relative;
    margin-left: 0.5rem;
    vertical-align: middle;
  }}
  .score-fill {{
    height: 100%;
    border-radius: 9px;
    transition: width 0.3s;
  }}
  .score-label {{
    position: absolute;
    width: 100%;
    text-align: center;
    font-size: 0.7rem;
    font-weight: 600;
    color: white;
    text-shadow: 0 1px 2px rgba(0,0,0,0.5);
  }}

  /* Scenario sections */
  .scenario {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    margin-bottom: 1rem;
    overflow: hidden;
  }}
  .scenario-header {{
    padding: 1rem 1.25rem;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
  }}
  .scenario-header:hover {{ background: var(--surface-2); }}
  .scenario-title {{
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }}
  .scenario-toggle {{
    color: var(--text-muted);
    font-size: 0.8rem;
    transition: transform 0.2s;
    display: inline-block;
  }}
  .scenario-toggle.open {{ transform: rotate(90deg); }}
  .scenario-scores {{
    display: flex;
    gap: 0.75rem;
    flex-shrink: 0;
  }}
  .score-chip {{
    font-size: 0.8rem;
    color: var(--text-muted);
    background: var(--surface-2);
    padding: 0.2rem 0.6rem;
    border-radius: 4px;
  }}

  .scenario-body {{
    border-top: 1px solid var(--border);
    padding: 1.25rem;
  }}

  .prompt-section {{
    background: var(--surface-2);
    padding: 0.75rem 1rem;
    border-radius: 6px;
    margin-bottom: 1.25rem;
    font-size: 0.9rem;
    border-left: 3px solid var(--accent);
  }}

  /* Comparison grid */
  .comparison-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
  }}
  @media (max-width: 900px) {{
    .comparison-grid {{ grid-template-columns: 1fr; }}
  }}
  .comparison-col {{
    min-width: 0;
  }}

  /* Eval details */
  .eval-details {{
    margin-bottom: 1rem;
    font-size: 0.8rem;
  }}
  .eval-row {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.2rem 0;
  }}
  .eval-label {{
    min-width: 140px;
    color: var(--text-muted);
  }}
  .eval-ratio {{
    font-weight: 600;
    min-width: 40px;
  }}
  .eval-detail {{
    color: var(--text-muted);
    font-size: 0.75rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }}

  /* Timeline */
  .timeline {{
    border-left: 2px solid var(--border);
    padding-left: 1rem;
    margin-left: 0.5rem;
  }}
  .timeline-empty {{
    color: var(--text-muted);
    font-style: italic;
    padding: 1rem;
  }}
  .tl-event {{
    margin-bottom: 0.75rem;
    position: relative;
  }}
  .tl-event::before {{
    content: '';
    position: absolute;
    left: -1.35rem;
    top: 0.5rem;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--border);
  }}
  .tl-tool-call::before {{ background: var(--accent); }}
  .tl-tool-result::before {{ background: var(--yellow); }}
  .tl-text::before {{ background: var(--text-muted); }}

  .tl-badge {{
    display: inline-block;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--text-muted);
    margin-bottom: 0.2rem;
  }}
  .tl-badge-tool {{ color: var(--accent); }}
  .tl-badge-result {{ color: var(--yellow); }}

  .tl-body {{
    font-size: 0.85rem;
    color: var(--text);
    word-break: break-word;
  }}

  .tl-body.md-rendered {{
    white-space: normal;
  }}
  .tl-body.md-rendered p {{
    margin: 0.3em 0;
  }}
  .tl-body.md-rendered h1,
  .tl-body.md-rendered h2,
  .tl-body.md-rendered h3,
  .tl-body.md-rendered h4,
  .tl-body.md-rendered h5,
  .tl-body.md-rendered h6 {{
    margin: 0.5em 0 0.2em;
    font-size: 1em;
    color: var(--accent);
  }}
  .tl-body.md-rendered ul,
  .tl-body.md-rendered ol {{
    margin: 0.3em 0;
    padding-left: 1.5em;
  }}
  .tl-body.md-rendered li {{
    margin: 0.15em 0;
  }}
  .tl-body.md-rendered blockquote {{
    border-left: 3px solid var(--accent);
    padding-left: 0.75em;
    margin: 0.3em 0;
    color: var(--text-muted);
  }}
  .tl-body.md-rendered a {{
    color: var(--accent);
    text-decoration: none;
  }}
  .tl-body.md-rendered a:hover {{
    text-decoration: underline;
  }}
  .tl-body.md-rendered strong {{
    color: var(--text);
    font-weight: 600;
  }}
  .md-code-block {{
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.5rem;
    overflow-x: auto;
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 0.78rem;
    white-space: pre;
    margin: 0.3em 0;
  }}
  .md-inline-code {{
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 0.1em 0.3em;
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 0.85em;
  }}

  .tl-code {{
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 0.78rem;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.5rem;
    overflow-x: auto;
    max-height: 600px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-all;
  }}

  /* Scenario metrics bar */
  .scenario-metrics {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
    margin-bottom: 1.25rem;
    padding: 0.75rem;
    background: var(--surface-2);
    border-radius: 6px;
    border: 1px solid var(--border);
  }}
  .metric-group h5 {{
    font-size: 0.75rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 0.3rem;
  }}
  .metric-compare {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
  }}
  .metric-val {{
    font-size: 0.85rem;
    color: var(--text-muted);
  }}
  .metric-val strong {{
    color: var(--text);
  }}
  .metric-delta {{
    font-size: 0.8rem;
    font-weight: 600;
    padding: 0.1rem 0.4rem;
    border-radius: 4px;
  }}
  .metric-better {{
    color: var(--green);
    background: rgba(63, 185, 80, 0.1);
  }}
  .metric-worse {{
    color: var(--red);
    background: rgba(248, 81, 73, 0.1);
  }}

  /* Skill badges */
  .skill-badge {{
    display: inline-block;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 500;
    background: rgba(88, 166, 255, 0.12);
    color: var(--accent);
    border: 1px solid rgba(88, 166, 255, 0.25);
  }}
  .skill-none {{
    font-size: 0.8rem;
    color: var(--text-muted);
    font-style: italic;
  }}

  details {{ margin-top: 0.25rem; }}
  summary {{
    cursor: pointer;
    font-size: 0.8rem;
    color: var(--text-muted);
    user-select: none;
  }}
  summary:hover {{ color: var(--accent); }}

  /* Controls */
  .controls {{
    display: flex;
    gap: 0.75rem;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
  }}
  .controls button {{
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 0.4rem 0.8rem;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.85rem;
  }}
  .controls button:hover {{ background: var(--surface-2); border-color: var(--accent); }}
  .controls button.active {{ border-color: var(--accent); background: rgba(88, 166, 255, 0.1); }}

  .footer {{
    margin-top: 3rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
    text-align: center;
    color: var(--text-muted);
    font-size: 0.8rem;
  }}
</style>
</head>
<body>

<div class="header">
  <h1>Honeycomb Plugin &mdash; Scenario Comparison Report</h1>
  <p>Generated: {timestamp} &middot; {total} scenarios compared</p>
</div>

<div class="stats">
  <div class="stat-card">
    <span class="stat-value">{total}</span>
    <span class="stat-label">Scenarios</span>
  </div>
  <div class="stat-card">
    <span class="stat-value" style="color:var(--green)">{improved}</span>
    <span class="stat-label">Improved</span>
  </div>
  <div class="stat-card">
    <span class="stat-value">{neutral}</span>
    <span class="stat-label">Neutral</span>
  </div>
  <div class="stat-card">
    <span class="stat-value" style="color:var(--red)">{regressed}</span>
    <span class="stat-label">Regressed</span>
  </div>
  <div class="stat-card">
    <span class="stat-value">{avg_plugin:.2f}</span>
    <span class="stat-label">Avg Plugin Score</span>
  </div>
  <div class="stat-card">
    <span class="stat-value">{avg_baseline:.2f}</span>
    <span class="stat-label">Avg Baseline Score</span>
  </div>
  <div class="stat-card">
    <span class="stat-value" style="color:{'var(--green)' if avg_delta >= 0 else 'var(--red)'}">{"+" if avg_delta >= 0 else ""}{avg_delta:.2f}</span>
    <span class="stat-label">Avg Delta</span>
  </div>
  <div class="stat-card">
    <span class="stat-value">{avg_plugin_calls:.1f}</span>
    <span class="stat-label">Avg Plugin Tool Calls</span>
  </div>
  <div class="stat-card">
    <span class="stat-value">{avg_baseline_calls:.1f}</span>
    <span class="stat-label">Avg Baseline Tool Calls</span>
  </div>
  <div class="stat-card">
    <span class="stat-value">{_format_duration(total_plugin_dur)}</span>
    <span class="stat-label">Total Plugin Time</span>
  </div>
  <div class="stat-card">
    <span class="stat-value">{_format_duration(total_baseline_dur)}</span>
    <span class="stat-label">Total Baseline Time</span>
  </div>
</div>

<h2>Summary</h2>
<table class="summary-table">
  <thead>
    <tr>
      <th>Scenario</th>
      <th>Plugin Score</th>
      <th>Baseline Score</th>
      <th>Delta</th>
      <th>Plugin Calls</th>
      <th>Baseline Calls</th>
      <th>Plugin Time</th>
      <th>Baseline Time</th>
      <th>Verdict</th>
    </tr>
  </thead>
  <tbody>
    {summary_rows}
  </tbody>
</table>

<h2>Scenario Details</h2>
<div class="controls">
  <button onclick="expandAll()" title="Expand all scenarios">Expand All</button>
  <button onclick="collapseAll()" title="Collapse all scenarios">Collapse All</button>
  <button onclick="filterVerdict('all')" class="active" id="filter-all">All</button>
  <button onclick="filterVerdict('improved')" id="filter-improved">Improved</button>
  <button onclick="filterVerdict('neutral')" id="filter-neutral">Neutral</button>
  <button onclick="filterVerdict('regressed')" id="filter-regressed">Regressed</button>
</div>

<div id="scenarios">
  {scenario_sections}
</div>

<div class="footer">
  <p>Honeycomb Claude Code Plugin &middot; Comparison Report</p>
</div>

<script>
function toggleScenario(id) {{
  const body = document.getElementById('body-' + id);
  const toggle = document.getElementById('toggle-' + id);
  if (body.style.display === 'none') {{
    body.style.display = 'block';
    toggle.classList.add('open');
  }} else {{
    body.style.display = 'none';
    toggle.classList.remove('open');
  }}
}}

function expandAll() {{
  document.querySelectorAll('.scenario-body').forEach(el => el.style.display = 'block');
  document.querySelectorAll('.scenario-toggle').forEach(el => el.classList.add('open'));
}}

function collapseAll() {{
  document.querySelectorAll('.scenario-body').forEach(el => el.style.display = 'none');
  document.querySelectorAll('.scenario-toggle').forEach(el => el.classList.remove('open'));
}}

function filterVerdict(verdict) {{
  document.querySelectorAll('.controls button').forEach(b => b.classList.remove('active'));
  document.getElementById('filter-' + verdict).classList.add('active');

  document.querySelectorAll('.scenario').forEach(el => {{
    if (verdict === 'all') {{
      el.style.display = 'block';
    }} else {{
      el.style.display = el.dataset.verdict === verdict ? 'block' : 'none';
    }}
  }});
}}

function scrollToScenario(id) {{
  const el = document.getElementById('scenario-' + id);
  if (el) {{
    el.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
    // Expand it
    const body = document.getElementById('body-' + id);
    const toggle = document.getElementById('toggle-' + id);
    body.style.display = 'block';
    toggle.classList.add('open');
  }}
}}
</script>
</body>
</html>"""

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_html)
    return report_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate scenario comparison report")
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help=f"Output HTML path (default: {DEFAULT_REPORT_PATH})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Directory with scenario output (default: {OUTPUT_DIR})",
    )
    args = parser.parse_args()

    path = generate_report(output_dir=args.output_dir, report_path=args.output)
    print(f"Report generated: {path}")


if __name__ == "__main__":
    main()
