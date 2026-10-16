"""Unit tests: detection rules + both scenarios."""
from __future__ import annotations

import unittest

from agent_loop_breaker.agents import (
    DemoSummary,
    run_goodbye_loop,
    run_tool_retry_loop,
)
from agent_loop_breaker.breaker import BreakConfig, LoopBreaker, args_fingerprint
from agent_loop_breaker.normalize import farewell_fingerprint, is_farewell_like, normalize_text


class TestNormalize(unittest.TestCase):
    def test_farewell_variants(self):
        samples = [
            "Goodbye!",
            "bye bye — thanks again",
            "See you soon",
            "Take care, have a great day",
            "Thank you so much for the interview",
            "Farewell for now",
            "Cheers, talk later",
        ]
        for s in samples:
            self.assertTrue(is_farewell_like(s), msg=s)
            self.assertEqual(farewell_fingerprint(s), "FAREWELL")

    def test_non_farewell(self):
        self.assertFalse(is_farewell_like("Walk me through your Kafka consumer lag strategy."))
        self.assertNotEqual(
            farewell_fingerprint("Walk me through your Kafka consumer lag strategy."),
            "FAREWELL",
        )

    def test_normalize_collapses(self):
        self.assertEqual(normalize_text("Hello,  World!"), "hello world")


class TestBreakerRules(unittest.TestCase):
    def test_farewell_streak_trips(self):
        b = LoopBreaker(BreakConfig(farewell_streak=4, window_n=10, repetition_threshold=0.99))
        for i, t in enumerate(["Goodbye!", "Bye!", "See you!", "Thanks, take care!"]):
            d = b.observe_turn(t)
            if i < 3:
                self.assertFalse(d.broken, msg=t)
            else:
                self.assertTrue(d.broken)
                self.assertEqual(d.rule, "farewell_streak")

    def test_text_repetition_ratio(self):
        # High threshold window: force dominant FAREWELL ratio
        b = LoopBreaker(
            BreakConfig(farewell_streak=99, window_n=4, repetition_threshold=0.75)
        )
        for t in ["Goodbye", "Bye", "See you", "Thanks"]:
            d = b.observe_turn(t)
        self.assertTrue(d.broken)
        self.assertEqual(d.rule, "text_repetition")

    def test_tool_args_repeat(self):
        b = LoopBreaker(BreakConfig(tool_repeat_k=3))
        args = {"query": "AI agent engineer", "limit": 10}
        for i in range(3):
            d = b.observe_tool("search_jobs", args)
            if i < 2:
                self.assertFalse(d.broken)
            else:
                self.assertTrue(d.broken)
                self.assertEqual(d.rule, "tool_args_repeat")

    def test_different_args_no_trip(self):
        b = LoopBreaker(BreakConfig(tool_repeat_k=3))
        for i in range(5):
            d = b.observe_tool("search_jobs", {"query": f"q{i}"})
            self.assertFalse(d.broken)

    def test_args_fingerprint_stable(self):
        a = {"b": 2, "a": 1}
        self.assertEqual(args_fingerprint("t", a), args_fingerprint("t", {"a": 1, "b": 2}))

    def test_disabled_never_breaks(self):
        b = LoopBreaker(BreakConfig(farewell_streak=2), enabled=False)
        for _ in range(10):
            self.assertFalse(b.observe_turn("Goodbye!").broken)


class TestScenarios(unittest.TestCase):
    def test_goodbye_breaks_mid_run(self):
        cfg = BreakConfig(max_turns=40, farewell_streak=4, window_n=6, repetition_threshold=0.75)
        ctrl = run_goodbye_loop(breaker_on=False, config=cfg)
        brk = run_goodbye_loop(breaker_on=True, config=cfg)
        self.assertFalse(ctrl.broken)
        self.assertEqual(ctrl.turns_run, 40)
        self.assertTrue(brk.broken)
        self.assertLess(brk.turns_run, ctrl.turns_run)
        self.assertIn(brk.break_rule, ("farewell_streak", "text_repetition"))

    def test_tool_retry_breaks_at_k(self):
        cfg = BreakConfig(tool_repeat_k=3, max_turns=20)
        ctrl = run_tool_retry_loop(breaker_on=False, config=cfg, max_calls=20)
        brk = run_tool_retry_loop(breaker_on=True, config=cfg, max_calls=20)
        self.assertFalse(ctrl.broken)
        self.assertEqual(ctrl.tool_calls_run, 20)
        self.assertTrue(brk.broken)
        self.assertEqual(brk.break_rule, "tool_args_repeat")
        self.assertEqual(brk.tool_calls_run, 3)

    def test_demo_summary_pass(self):
        cfg = BreakConfig(max_turns=40, farewell_streak=4, tool_repeat_k=3)
        summary = DemoSummary(
            goodbye_control=run_goodbye_loop(breaker_on=False, config=cfg),
            goodbye_break=run_goodbye_loop(breaker_on=True, config=cfg),
            tool_control=run_tool_retry_loop(breaker_on=False, config=cfg, max_calls=40),
            tool_break=run_tool_retry_loop(breaker_on=True, config=cfg, max_calls=40),
        )
        summary.compute()
        self.assertEqual(summary.loops_detected, 2)
        self.assertGreater(summary.turns_saved, 0)
        self.assertGreater(summary.tokens_saved_est, 0)
        self.assertEqual(summary.escaped, 0)
        self.assertTrue(summary.passed)


if __name__ == "__main__":
    unittest.main()
