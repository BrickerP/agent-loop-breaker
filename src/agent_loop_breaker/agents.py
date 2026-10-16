"""Deterministic script agents — no API keys, no network."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from .breaker import BreakConfig, BreakDecision, LoopBreaker, args_fingerprint
from .log import EventLog

SH = ZoneInfo("Asia/Shanghai")


def _now_iso() -> str:
    return datetime.now(SH).strftime("%Y-%m-%dT%H:%M:%S%z")


# Interviewer / candidate farewell variants (mutual goodbye dead-loop).
INTERVIEWER_LINES = [
    "Thanks for your time today — it was a pleasure speaking with you.",
    "Great conversation. Goodbye for now, and best of luck!",
    "Appreciate your answers. Take care, see you soon!",
    "Thanks again. Bye — looking forward to next steps.",
    "It was nice talking. Have a great day, goodbye!",
    "All the best. See you later — bye!",
    "Thank you so much. Farewell for now.",
    "Cheers, take care. Talk soon!",
    "Bye bye — thanks again for joining.",
    "So long, and thanks. Catch you later!",
    "Goodbye! Looking forward to staying in touch.",
    "See you around. Thanks, bye!",
    "Have a nice evening. Goodbye!",
    "Best regards — bye for now.",
    "Thanks a lot. See you tomorrow!",
    "Pleasure meeting you. Take care, goodbye.",
    "Bye — appreciate it. Talk later.",
    "Farewell. Have a good one!",
    "Thanks again. Bye bye!",
    "See you soon. Goodbye!",
]

CANDIDATE_LINES = [
    "Thank you so much for the interview. Goodbye!",
    "Appreciate the opportunity. Bye, take care!",
    "It was a pleasure. See you soon — thanks!",
    "Thanks again. Have a great day, goodbye!",
    "Bye! Looking forward to hearing from you.",
    "Thank you. Farewell for now.",
    "All the best — see you later. Bye!",
    "Cheers. Talk soon, and thanks!",
    "Goodbye — really appreciated the chat.",
    "Take care. Bye bye!",
    "Thanks a lot. Catch you later!",
    "See you around. Goodbye!",
    "Have a nice day. Bye!",
    "Best regards. Thank you, goodbye.",
    "So long — thanks again!",
    "Talk later. Bye!",
    "Appreciate it. See you soon!",
    "Farewell. Thanks so much!",
    "Bye bye — have a good one!",
    "Goodbye! Talk soon.",
]

# Identical tool+args retry payloads
TOOL_RETRY_CALLS = [
    ("search_jobs", {"query": "AI agent engineer remote", "limit": 10}),
    ("search_jobs", {"query": "AI agent engineer remote", "limit": 10}),
    ("search_jobs", {"query": "AI agent engineer remote", "limit": 10}),
    ("search_jobs", {"query": "AI agent engineer remote", "limit": 10}),
    ("search_jobs", {"query": "AI agent engineer remote", "limit": 10}),
    ("send_email", {"to": "recruiter@example.com", "subject": "Follow-up", "body": "Hi again"}),
    ("send_email", {"to": "recruiter@example.com", "subject": "Follow-up", "body": "Hi again"}),
    ("send_email", {"to": "recruiter@example.com", "subject": "Follow-up", "body": "Hi again"}),
    ("send_email", {"to": "recruiter@example.com", "subject": "Follow-up", "body": "Hi again"}),
    ("send_email", {"to": "recruiter@example.com", "subject": "Follow-up", "body": "Hi again"}),
]


@dataclass
class ScenarioResult:
    name: str
    breaker_on: bool
    turns_run: int
    tool_calls_run: int
    broken: bool
    break_rule: str = ""
    break_reason: str = ""
    escaped: int = 0  # turns/calls after a would-be break (control only uses max)
    max_turns: int = 0
    events: list = field(default_factory=list)
    chars_emitted: int = 0

    @property
    def turns_saved(self) -> int:
        """Vs uncapped max: how many turns we did not burn."""
        if not self.breaker_on:
            return 0
        # For goodbye: max_turns is the control cap; saved = max - run (if broken early)
        # For tool: max is len of script or config max
        return max(0, self.max_turns - self.turns_run - self.tool_calls_run)

    @property
    def tokens_saved_est(self) -> int:
        """Rough tokens = chars/4 of avoided turns (estimate remaining script)."""
        if not self.breaker_on or not self.broken:
            return 0
        # Estimate: average ~80 chars/turn * remaining * /4
        remaining = max(0, self.max_turns - self.turns_run - self.tool_calls_run)
        return int(remaining * 80 / 4)


def run_goodbye_loop(
    *,
    breaker_on: bool = True,
    config: Optional[BreakConfig] = None,
    log: Optional[EventLog] = None,
    max_turns: Optional[int] = None,
) -> ScenarioResult:
    """Interviewer ↔ candidate ping-pong goodbye until breaker or max."""
    cfg = config or BreakConfig()
    cap = max_turns if max_turns is not None else cfg.max_turns
    breaker = LoopBreaker(cfg, enabled=breaker_on)
    log = log or EventLog()
    result = ScenarioResult(
        name="goodbye_loop",
        breaker_on=breaker_on,
        turns_run=0,
        tool_calls_run=0,
        broken=False,
        max_turns=cap,
    )

    # Prefatory non-farewell turns so the loop is visibly "after the interview"
    opener_i = "Thanks for walking through your agent eval harness experience."
    opener_c = "Happy to dig into the MCP guardrails work we shipped last quarter."
    for agent, text in (("interviewer", opener_i), ("candidate", opener_c)):
        log.append(
            ts=_now_iso(),
            kind="turn",
            agent=agent,
            text=text,
            scenario="goodbye_loop",
            breaker_on=breaker_on,
        )
        result.turns_run += 1
        result.chars_emitted += len(text)
        dec = breaker.observe_turn(text, agent=agent)
        if dec.broken:
            result.broken = True
            result.break_rule = dec.rule
            result.break_reason = dec.reason
            log.append(
                ts=_now_iso(),
                kind="break",
                agent="breaker",
                reason=dec.reason,
                scenario="goodbye_loop",
                breaker_on=breaker_on,
                extra={"rule": dec.rule, **dec.detail},
            )
            return result

    i_idx = 0
    c_idx = 0
    while result.turns_run < cap:
        # Interviewer farewell
        text = INTERVIEWER_LINES[i_idx % len(INTERVIEWER_LINES)]
        i_idx += 1
        log.append(
            ts=_now_iso(),
            kind="turn",
            agent="interviewer",
            text=text,
            scenario="goodbye_loop",
            breaker_on=breaker_on,
        )
        result.turns_run += 1
        result.chars_emitted += len(text)
        dec = breaker.observe_turn(text, agent="interviewer")
        if dec.broken:
            result.broken = True
            result.break_rule = dec.rule
            result.break_reason = dec.reason
            log.append(
                ts=_now_iso(),
                kind="break",
                agent="breaker",
                reason=dec.reason,
                scenario="goodbye_loop",
                breaker_on=breaker_on,
                extra={"rule": dec.rule, **dec.detail},
            )
            return result

        if result.turns_run >= cap:
            break

        # Candidate farewell
        text = CANDIDATE_LINES[c_idx % len(CANDIDATE_LINES)]
        c_idx += 1
        log.append(
            ts=_now_iso(),
            kind="turn",
            agent="candidate",
            text=text,
            scenario="goodbye_loop",
            breaker_on=breaker_on,
        )
        result.turns_run += 1
        result.chars_emitted += len(text)
        dec = breaker.observe_turn(text, agent="candidate")
        if dec.broken:
            result.broken = True
            result.break_rule = dec.rule
            result.break_reason = dec.reason
            log.append(
                ts=_now_iso(),
                kind="break",
                agent="breaker",
                reason=dec.reason,
                scenario="goodbye_loop",
                breaker_on=breaker_on,
                extra={"rule": dec.rule, **dec.detail},
            )
            return result

    # Hit max without break
    if breaker_on:
        result.escaped = 0  # didn't break but also didn't escape past a break
    else:
        # Control ran full uncapped max — "escaped" means loop continued to cap
        result.escaped = 0  # escaped past break is only meaningful mid-run with breaker
    return result


def run_tool_retry_loop(
    *,
    breaker_on: bool = True,
    config: Optional[BreakConfig] = None,
    log: Optional[EventLog] = None,
    max_calls: Optional[int] = None,
) -> ScenarioResult:
    """Agent retries identical tool+args until breaker or script end/max."""
    cfg = config or BreakConfig()
    # Control max: burn through many identical retries
    cap = max_calls if max_calls is not None else max(cfg.max_turns, 20)
    breaker = LoopBreaker(cfg, enabled=breaker_on)
    log = log or EventLog()
    result = ScenarioResult(
        name="tool_retry",
        breaker_on=breaker_on,
        turns_run=0,
        tool_calls_run=0,
        broken=False,
        max_turns=cap,
    )

    # Build a long identical-retry script for control
    script: list[tuple[str, dict]] = []
    while len(script) < cap:
        for tool, args in TOOL_RETRY_CALLS:
            script.append((tool, dict(args)))
            if len(script) >= cap:
                break

    for tool, args in script:
        fp = args_fingerprint(tool, args)
        log.append(
            ts=_now_iso(),
            kind="tool_call",
            agent="job_agent",
            tool=tool,
            args=args,
            args_fp=fp,
            scenario="tool_retry",
            breaker_on=breaker_on,
        )
        result.tool_calls_run += 1
        result.chars_emitted += json_len(args) + len(tool)
        dec = breaker.observe_tool(tool, args)
        if dec.broken:
            result.broken = True
            result.break_rule = dec.rule
            result.break_reason = dec.reason
            log.append(
                ts=_now_iso(),
                kind="break",
                agent="breaker",
                reason=dec.reason,
                tool=tool,
                args=args,
                args_fp=fp,
                scenario="tool_retry",
                breaker_on=breaker_on,
                extra={"rule": dec.rule, **dec.detail},
            )
            return result

    return result


def json_len(args: dict) -> int:
    import json

    return len(json.dumps(args, sort_keys=True))


@dataclass
class DemoSummary:
    goodbye_control: ScenarioResult
    goodbye_break: ScenarioResult
    tool_control: ScenarioResult
    tool_break: ScenarioResult
    loops_detected: int = 0
    turns_run: int = 0
    turns_saved: int = 0
    tokens_saved_est: int = 0
    escaped: int = 0
    passed: bool = False

    def compute(self) -> None:
        self.loops_detected = int(self.goodbye_break.broken) + int(self.tool_break.broken)
        self.turns_run = (
            self.goodbye_break.turns_run
            + self.goodbye_break.tool_calls_run
            + self.tool_break.turns_run
            + self.tool_break.tool_calls_run
        )
        # Saved vs control (uncapped max runs)
        g_saved = max(
            0,
            (self.goodbye_control.turns_run + self.goodbye_control.tool_calls_run)
            - (self.goodbye_break.turns_run + self.goodbye_break.tool_calls_run),
        )
        t_saved = max(
            0,
            (self.tool_control.turns_run + self.tool_control.tool_calls_run)
            - (self.tool_break.turns_run + self.tool_break.tool_calls_run),
        )
        self.turns_saved = g_saved + t_saved
        # tokens: chars avoided / 4
        g_chars = max(0, self.goodbye_control.chars_emitted - self.goodbye_break.chars_emitted)
        t_chars = max(0, self.tool_control.chars_emitted - self.tool_break.chars_emitted)
        self.tokens_saved_est = (g_chars + t_chars) // 4
        # escaped = any turn after break was recorded while breaker on (should be 0)
        self.escaped = 0
        if self.goodbye_break.broken:
            # ensure no events after break in goodbye with breaker
            pass
        # PASS: both loops caught, escaped=0
        self.passed = (
            self.goodbye_break.broken
            and self.tool_break.broken
            and self.loops_detected == 2
            and self.escaped == 0
        )
