# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class Fold:
    reason: str
    summary: str
    replaced_events: int

    def to_text(self) -> str:
        return (
            f"- reason: {self.reason}\n"
            f"  replaced_events: {self.replaced_events}\n"
            f"  summary: {self.summary}"
        )


def naive_summarize_events(events: List[str], max_lines: int = 10) -> str:
    """
    Very simple summarizer (offline, no LLM). Keeps signal only.
    """
    lines = []
    for e in events:
        e = e.strip()
        if not e:
            continue
        # keep only first line of each event
        first = e.split("\n", 1)[0].strip()
        lines.append(first)
        if len(lines) >= max_lines:
            break
    if not lines:
        return "(empty)"
    return " | ".join(lines)
