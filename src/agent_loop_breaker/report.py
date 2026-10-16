"""HTML report + RESULT summary text."""
from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .agents import DemoSummary, ScenarioResult
from .log import EventLog

SH = ZoneInfo("Asia/Shanghai")


def _esc(x: Any) -> str:
    return html.escape(str(x))


def summary_text(summary: DemoSummary) -> str:
    overall = "PASS" if summary.passed else "FAIL"
    lines = [
        f"RESULT: {overall}",
        f"  loops_detected={summary.loops_detected}  turns_run={summary.turns_run}  "
        f"turns_saved={summary.turns_saved}  tokens_saved_est={summary.tokens_saved_est}  "
        f"escaped={summary.escaped}",
        f"  goodbye: control_turns={summary.goodbye_control.turns_run}  "
        f"break_turns={summary.goodbye_break.turns_run}  "
        f"rule={summary.goodbye_break.break_rule or '-'}",
        f"  tool_retry: control_calls={summary.tool_control.tool_calls_run}  "
        f"break_calls={summary.tool_break.tool_calls_run}  "
        f"rule={summary.tool_break.break_rule or '-'}",
    ]
    return "\n".join(lines)


def write_report(
    summary: DemoSummary,
    log: EventLog,
    out_path: Path,
    title: str = "agent-loop-breaker · goodbye-loop demo",
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    overall = "PASS" if summary.passed else "FAIL"
    overall_cls = "pass" if summary.passed else "fail"
    now = datetime.now(SH).strftime("%Y-%m-%d %H:%M CST")

    def scen_row(label: str, ctrl: ScenarioResult, brk: ScenarioResult) -> str:
        return (
            f"<tr>"
            f"<td>{_esc(label)}</td>"
            f"<td>{ctrl.turns_run + ctrl.tool_calls_run}</td>"
            f"<td>{brk.turns_run + brk.tool_calls_run}</td>"
            f"<td class='{'pass' if brk.broken else 'fail'}'>"
            f"<strong>{'BROKEN' if brk.broken else 'NO BREAK'}</strong></td>"
            f"<td><code>{_esc(brk.break_rule or '-')}</code></td>"
            f"<td>{_esc((brk.break_reason or '-')[:120])}</td>"
            f"</tr>"
        )

    event_rows = []
    for e in log.events:
        cls = "break" if e.kind == "break" else ("tool" if e.kind == "tool_call" else "turn")
        body = e.text or e.tool or e.reason
        if e.args:
            body = f"{e.tool}({e.args})"
        if len(str(body)) > 100:
            body = str(body)[:97] + "..."
        event_rows.append(
            f"<tr class='{cls}'>"
            f"<td>{e.seq}</td>"
            f"<td><code>{_esc(e.kind)}</code></td>"
            f"<td>{_esc(e.agent)}</td>"
            f"<td>{_esc(e.scenario)}</td>"
            f"<td>{'on' if e.breaker_on else 'off'}</td>"
            f"<td><code>{_esc(body)}</code></td>"
            f"</tr>"
        )

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{_esc(title)} — {overall}</title>
<style>
  :root {{
    --bg: #0b1220; --card: #121a2b; --text: #e7eefc; --muted: #9aa8c7;
    --pass: #3dd68c; --fail: #ff6b6b; --break: #f0c14b; --line: #243047; --accent: #6ea8fe;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
    background: radial-gradient(1200px 600px at 10% -10%, #1a2744, var(--bg));
    color: var(--text); line-height: 1.5; padding: 32px 20px 64px;
  }}
  main {{ max-width: 1100px; margin: 0 auto; }}
  .hero {{
    background: linear-gradient(135deg, #152238, #10182a 60%);
    border: 1px solid var(--line); border-radius: 16px; padding: 28px;
    margin-bottom: 24px;
  }}
  h1 {{ margin: 0 0 8px; font-size: 1.6rem; }}
  .badge {{
    display: inline-block; padding: 4px 12px; border-radius: 999px; font-size: 0.85rem;
    font-weight: 700; letter-spacing: 0.04em; margin-left: 8px;
  }}
  .badge.pass {{ background: rgba(61,214,140,0.15); color: var(--pass); border: 1px solid var(--pass); }}
  .badge.fail {{ background: rgba(255,107,107,0.15); color: var(--fail); border: 1px solid var(--fail); }}
  .muted {{ color: var(--muted); }}
  .metrics {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 12px; margin: 20px 0 8px;
  }}
  .metric {{
    background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px;
  }}
  .metric .n {{ font-size: 1.8rem; font-weight: 700; font-variant-numeric: tabular-nums; }}
  .metric .l {{ color: var(--muted); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.06em; }}
  .metric.ok .n {{ color: var(--pass); }}
  .metric.bad .n {{ color: var(--fail); }}
  .metric.warn .n {{ color: var(--break); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; margin-top: 12px; }}
  th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--line); vertical-align: top; }}
  th {{ color: var(--muted); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; }}
  tr.break {{ background: rgba(240,193,75,0.08); }}
  tr.tool {{ background: rgba(110,168,254,0.05); }}
  td.pass {{ color: var(--pass); }}
  td.fail {{ color: var(--fail); }}
  code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.85em; }}
  h2 {{ margin: 28px 0 8px; font-size: 1.15rem; }}
  .card {{
    background: var(--card); border: 1px solid var(--line); border-radius: 12px;
    padding: 16px 18px; margin-bottom: 16px;
  }}
</style>
</head>
<body>
<main>
  <section class="hero">
    <h1>{_esc(title)} <span class="badge {overall_cls}">{overall}</span></h1>
    <p class="muted">Self-use: simulated interviewer ↔ candidate goodbye dead-loop + identical tool+args retry.
    Heat: AI recruiter/candidate bots stuck saying goodbye (~56s viral clip) · Guardian AI rollback/cleanup cost.
    Generated {now}.</p>
    <div class="metrics">
      <div class="metric ok"><div class="n">{summary.loops_detected}</div><div class="l">loops detected</div></div>
      <div class="metric"><div class="n">{summary.turns_run}</div><div class="l">turns/calls run</div></div>
      <div class="metric ok"><div class="n">{summary.turns_saved}</div><div class="l">turns saved</div></div>
      <div class="metric ok"><div class="n">{summary.tokens_saved_est}</div><div class="l">tokens saved est</div></div>
      <div class="metric ok"><div class="n">{summary.escaped}</div><div class="l">escaped</div></div>
    </div>
  </section>

  <section class="card">
    <h2>Scenarios (control vs breaker)</h2>
    <table>
      <thead><tr><th>Scenario</th><th>Control</th><th>With breaker</th><th>Break?</th><th>Rule</th><th>Reason</th></tr></thead>
      <tbody>
        {scen_row("A · goodbye ping-pong", summary.goodbye_control, summary.goodbye_break)}
        {scen_row("B · tool+args retry", summary.tool_control, summary.tool_break)}
      </tbody>
    </table>
  </section>

  <section class="card">
    <h2>Append-only event log ({len(log.events)} events)</h2>
    <table>
      <thead><tr><th>#</th><th>Kind</th><th>Agent</th><th>Scenario</th><th>Breaker</th><th>Payload</th></tr></thead>
      <tbody>
        {''.join(event_rows)}
      </tbody>
    </table>
  </section>

  <p class="muted">stdlib Python · zero deps · no API keys ·
  <a href="https://github.com/BrickerP/agent-loop-breaker" style="color:var(--accent)">BrickerP/agent-loop-breaker</a> ·
  hire: <a href="https://brickerp.github.io/hire/" style="color:var(--accent)">brickerp.github.io/hire</a></p>
</main>
</body>
</html>
"""
    out_path.write_text(doc, encoding="utf-8")
    return out_path
