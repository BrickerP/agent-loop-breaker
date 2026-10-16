#!/usr/bin/env python3
"""Generate dark RESULT card PNG for agent-loop-breaker (matplotlib Agg)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

BG, FG, MUTED = "#0B0B0C", "#F2F2F2", "#8A8A8F"
ACCENT = "#3DDC97"
WARN = "#F0C14B"


def parse_result(terminal_path: Path) -> dict:
    text = terminal_path.read_text(encoding="utf-8")
    out = {
        "status": "PASS" if "RESULT: PASS" in text else "FAIL",
        "loops_detected": 0,
        "turns_run": 0,
        "turns_saved": 0,
        "tokens_saved_est": 0,
        "escaped": 0,
    }
    m = re.search(
        r"loops_detected=(\d+)\s+turns_run=(\d+)\s+turns_saved=(\d+)\s+"
        r"tokens_saved_est=(\d+)\s+escaped=(\d+)",
        text,
    )
    if m:
        out["loops_detected"] = int(m.group(1))
        out["turns_run"] = int(m.group(2))
        out["turns_saved"] = int(m.group(3))
        out["tokens_saved_est"] = int(m.group(4))
        out["escaped"] = int(m.group(5))
    return out


def render(stats: dict, output: Path, size=(1600, 900)) -> None:
    w, h = size
    fig = plt.figure(figsize=(w / 100, h / 100), dpi=100, facecolor=BG)

    fig.text(0.05, 0.90, "Agent goodbye-loop breaker", color=FG, fontsize=36, weight="bold", va="bottom")
    fig.text(
        0.05,
        0.84,
        "Recruiter ↔ candidate farewell ping-pong + identical tool+args retry",
        color=MUTED,
        fontsize=18,
        va="top",
    )

    ax_badge = fig.add_axes([0.72, 0.78, 0.23, 0.14], facecolor=BG)
    ax_badge.set_xlim(0, 1)
    ax_badge.set_ylim(0, 1)
    ax_badge.axis("off")
    color = ACCENT if stats["status"] == "PASS" else "#FF6B6B"
    box = FancyBboxPatch(
        (0.05, 0.15), 0.9, 0.7,
        boxstyle="round,pad=0.04,rounding_size=0.08",
        linewidth=2, edgecolor=color, facecolor=color + "22",
    )
    ax_badge.add_patch(box)
    ax_badge.text(0.5, 0.55, "RESULT", color=MUTED, fontsize=14, ha="center", va="center", weight="bold")
    ax_badge.text(0.5, 0.28, stats["status"], color=color, fontsize=32, ha="center", va="center", weight="bold")

    metrics = [
        ("loops_detected", stats["loops_detected"], ACCENT),
        ("turns_saved", stats["turns_saved"], ACCENT),
        ("tokens_saved_est", stats["tokens_saved_est"], WARN),
        ("escaped", stats["escaped"], ACCENT),
    ]
    ax = fig.add_axes([0.08, 0.18, 0.84, 0.52], facecolor=BG)
    labels = [m[0] for m in metrics]
    vals = [m[1] for m in metrics]
    colors = [m[2] for m in metrics]
    bars = ax.barh(labels[::-1], vals[::-1], color=colors[::-1], height=0.55)
    mx = max(vals) if vals else 1
    ax.set_xlim(0, mx * 1.25 if mx else 1)
    ax.set_xticks([])
    ax.tick_params(axis="y", colors=FG, labelsize=22, length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    for bar, v in zip(bars, vals[::-1]):
        ax.text(v + mx * 0.02, bar.get_y() + bar.get_height() / 2, f"{v:,}",
                va="center", color=FG, fontsize=26, weight="bold")

    fig.text(0.05, 0.08,
             f"turns_run={stats['turns_run']}  ·  stdlib Python  ·  zero deps  ·  no API keys",
             color=MUTED, fontsize=14)
    fig.text(0.05, 0.04, "Source: BrickerP/agent-loop-breaker demo-goodbye-loop · 2026-10-16",
             color=MUTED, fontsize=13)
    fig.text(0.95, 0.04, "Yupeng Lu · @trashConsumer", color=MUTED, fontsize=14, ha="right")

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, facecolor=BG)
    plt.close(fig)
    print(output)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    terminal = root / "docs" / "demo-terminal.txt"
    stats = parse_result(terminal)
    out = root / "docs" / "demo-card.png"
    render(stats, out)
    (root / "docs" / "demo-card.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
