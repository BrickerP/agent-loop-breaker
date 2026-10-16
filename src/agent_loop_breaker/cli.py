"""CLI: python -m agent_loop_breaker demo | demo-goodbye-loop"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .agents import DemoSummary, run_goodbye_loop, run_tool_retry_loop
from .breaker import BreakConfig
from .log import EventLog
from .report import summary_text, write_report


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _run_demo(args: argparse.Namespace) -> int:
    root = _repo_root()
    report_path = Path(args.report) if args.report else root / "docs" / "demo-report.html"
    log_path = Path(args.log) if getattr(args, "log", None) else root / "docs" / "demo-events.jsonl"

    cfg = BreakConfig(
        window_n=getattr(args, "window_n", 6) or 6,
        repetition_threshold=getattr(args, "repetition_threshold", 0.75) or 0.75,
        farewell_streak=getattr(args, "farewell_streak", 4) or 4,
        tool_repeat_k=getattr(args, "tool_repeat_k", 3) or 3,
        max_turns=getattr(args, "max_turns", 40) or 40,
    )

    print("agent-loop-breaker demo-goodbye-loop")
    print("=" * 56)
    print("Use case: two deterministic script agents reproduce")
    print("  (A) mutual goodbye dead-loop (recruiter ↔ candidate)")
    print("  (B) identical tool+args retry (search_jobs / send_email)")
    print("Breaker trips mid-run; control run shows uncapped thrash.")
    print("Heat: viral AI goodbye-loop (~56s) + Guardian rollback cost.")
    print()
    print(f"config: window_n={cfg.window_n}  repetition_threshold={cfg.repetition_threshold}")
    print(f"        farewell_streak={cfg.farewell_streak}  tool_repeat_k={cfg.tool_repeat_k}")
    print(f"        max_turns={cfg.max_turns}")
    print()

    log = EventLog(log_path)

    print("Scenario A · goodbye ping-pong (control, breaker OFF)")
    print("-" * 56)
    g_ctrl = run_goodbye_loop(breaker_on=False, config=cfg, log=log, max_turns=cfg.max_turns)
    print(f"  turns_run={g_ctrl.turns_run}  broken={g_ctrl.broken}")

    print("Scenario A · goodbye ping-pong (breaker ON)")
    print("-" * 56)
    g_brk = run_goodbye_loop(breaker_on=True, config=cfg, log=log, max_turns=cfg.max_turns)
    print(f"  turns_run={g_brk.turns_run}  broken={g_brk.broken}  rule={g_brk.break_rule}")
    if g_brk.break_reason:
        print(f"  reason: {g_brk.break_reason}")

    print()
    print("Scenario B · tool+args retry (control, breaker OFF)")
    print("-" * 56)
    t_ctrl = run_tool_retry_loop(breaker_on=False, config=cfg, log=log, max_calls=cfg.max_turns)
    print(f"  tool_calls_run={t_ctrl.tool_calls_run}  broken={t_ctrl.broken}")

    print("Scenario B · tool+args retry (breaker ON)")
    print("-" * 56)
    t_brk = run_tool_retry_loop(breaker_on=True, config=cfg, log=log, max_calls=cfg.max_turns)
    print(f"  tool_calls_run={t_brk.tool_calls_run}  broken={t_brk.broken}  rule={t_brk.break_rule}")
    if t_brk.break_reason:
        print(f"  reason: {t_brk.break_reason}")

    summary = DemoSummary(
        goodbye_control=g_ctrl,
        goodbye_break=g_brk,
        tool_control=t_ctrl,
        tool_break=t_brk,
    )
    summary.compute()

    print("-" * 56)
    print(summary_text(summary))
    write_report(summary, log, report_path)
    print(f"  event log → {log_path}")
    print(f"  HTML report → {report_path}")
    return 0 if summary.passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agent-loop-breaker",
        description="Trip agent goodbye / tool-retry dead-loops mid-run (stdlib, zero deps).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add_demo_flags(p: argparse.ArgumentParser) -> None:
        p.add_argument("--report", default=None, help="HTML report path")
        p.add_argument("--log", default=None, help="JSONL event log path")
        p.add_argument("--window-n", dest="window_n", type=int, default=6)
        p.add_argument("--repetition-threshold", dest="repetition_threshold", type=float, default=0.75)
        p.add_argument("--farewell-streak", dest="farewell_streak", type=int, default=4)
        p.add_argument("--tool-repeat-k", dest="tool_repeat_k", type=int, default=3)
        p.add_argument("--max-turns", dest="max_turns", type=int, default=40)
        p.set_defaults(func=_run_demo)

    add_demo_flags(sub.add_parser("demo", help="Run full E2E demo (alias of demo-goodbye-loop)"))
    add_demo_flags(
        sub.add_parser("demo-goodbye-loop", help="Goodbye ping-pong + tool-retry breaker demo")
    )

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
