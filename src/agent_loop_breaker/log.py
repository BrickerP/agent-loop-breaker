"""Append-only JSONL event log for agent turns / tool calls."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class Event:
    seq: int
    ts: str
    kind: str  # turn | tool_call | break
    agent: str = ""
    text: str = ""
    tool: str = ""
    args: dict = field(default_factory=dict)
    args_fp: str = ""
    reason: str = ""
    scenario: str = ""
    breaker_on: bool = True
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if not d["extra"]:
            d.pop("extra")
        return d


class EventLog:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else None
        self.events: list[Event] = []
        self._seq = 0
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists():
                self.path.write_text("", encoding="utf-8")

    def append(self, **kwargs: Any) -> Event:
        self._seq += 1
        ev = Event(seq=self._seq, **kwargs)
        self.events.append(ev)
        if self.path:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(ev.to_dict(), ensure_ascii=False) + "\n")
        return ev

    def dump(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self.events]
