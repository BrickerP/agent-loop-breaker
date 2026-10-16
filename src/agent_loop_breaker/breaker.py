"""LoopBreaker: text-repetition + identical tool+args consecutive rules."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Optional

from .normalize import farewell_fingerprint, is_farewell_like, normalize_text


def args_fingerprint(tool: str, args: dict | None) -> str:
    payload = json.dumps({"tool": tool, "args": args or {}}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass
class BreakConfig:
    """Configurable break rules."""

    window_n: int = 6
    # Fraction of turns in the window that share the dominant fingerprint.
    repetition_threshold: float = 0.75
    # Also trip if ≥ this many consecutive turns are farewell-like.
    farewell_streak: int = 4
    # Same tool+args fingerprint consecutive K times.
    tool_repeat_k: int = 3
    max_turns: int = 40


@dataclass
class BreakDecision:
    broken: bool
    reason: str = ""
    rule: str = ""
    detail: dict = field(default_factory=dict)


class LoopBreaker:
    def __init__(self, config: Optional[BreakConfig] = None, enabled: bool = True) -> None:
        self.config = config or BreakConfig()
        self.enabled = enabled
        self.turn_fps: list[str] = []
        self.farewell_flags: list[bool] = []
        self.tool_fps: list[str] = []
        self.broken = False
        self.break_decision: Optional[BreakDecision] = None
        self.turns_seen = 0
        self.tool_calls_seen = 0

    def observe_turn(self, text: str, agent: str = "") -> BreakDecision:
        """Record a text turn; return break decision for this observation."""
        self.turns_seen += 1
        fp = farewell_fingerprint(text)
        self.turn_fps.append(fp)
        self.farewell_flags.append(is_farewell_like(text))

        if not self.enabled:
            return BreakDecision(False)
        if self.broken:
            return BreakDecision(True, reason=self.break_decision.reason if self.break_decision else "already_broken", rule="already")

        # Rule 1: consecutive farewell streak
        k = self.config.farewell_streak
        if len(self.farewell_flags) >= k and all(self.farewell_flags[-k:]):
            return self._trip(
                "farewell_streak",
                f"farewell-like text for {k} consecutive turns "
                f"(last agents ping-ponging goodbye/bye/thanks variants)",
                {"streak": k, "window_fps": self.turn_fps[-k:]},
            )

        # Rule 2: near-N repetition ratio
        n = self.config.window_n
        if len(self.turn_fps) >= n:
            window = self.turn_fps[-n:]
            # Dominant fingerprint share
            counts: dict[str, int] = {}
            for w in window:
                counts[w] = counts.get(w, 0) + 1
            dominant, dom_count = max(counts.items(), key=lambda kv: kv[1])
            ratio = dom_count / n
            if ratio >= self.config.repetition_threshold and dominant:
                return self._trip(
                    "text_repetition",
                    f"normalized text repetition ratio {ratio:.2f} ≥ "
                    f"{self.config.repetition_threshold} over last {n} turns "
                    f"(dominant={dominant!r})",
                    {"ratio": ratio, "dominant": dominant, "window": window},
                )

        return BreakDecision(False)

    def observe_tool(self, tool: str, args: dict | None = None) -> BreakDecision:
        """Record a tool call; trip if same tool+args fingerprint hits K consecutive."""
        self.tool_calls_seen += 1
        fp = args_fingerprint(tool, args)
        self.tool_fps.append(fp)

        if not self.enabled:
            return BreakDecision(False)
        if self.broken:
            return BreakDecision(True, reason=self.break_decision.reason if self.break_decision else "already_broken", rule="already")

        k = self.config.tool_repeat_k
        if len(self.tool_fps) >= k and len(set(self.tool_fps[-k:])) == 1:
            return self._trip(
                "tool_args_repeat",
                f"identical tool+args fingerprint {fp} for {k} consecutive calls "
                f"(tool={tool!r})",
                {"k": k, "fingerprint": fp, "tool": tool, "args": args or {}},
            )
        return BreakDecision(False)

    def _trip(self, rule: str, reason: str, detail: dict[str, Any]) -> BreakDecision:
        self.broken = True
        self.break_decision = BreakDecision(True, reason=reason, rule=rule, detail=detail)
        return self.break_decision
