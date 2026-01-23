# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from utils.text import normalize_newlines, strip_surrounding_whitespace_lines


@dataclass
class Fold:
    reason: str
    summary: str
    replaced_events: int
    created_utc: str

    @staticmethod
    def create(reason: str, summary: str, replaced_events: int) -> "Fold":
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return Fold(
            reason=normalize_newlines(reason).strip(),
            summary=strip_surrounding_whitespace_lines(summary),
            replaced_events=int(replaced_events),
            created_utc=ts,
        )

    def to_text(self) -> str:
        return (
            f"- [{self.created_utc}] reason={self.reason} replaced_events={self.replaced_events}\n"
            f"  summary:\n"
            f"{indent(self.summary, '    ')}"
        )


def indent(s: str, prefix: str) -> str:
    s = normalize_newlines(s)
    return "\n".join(prefix + line for line in s.split("\n"))


def naive_summarize_events(events: List[str], max_lines: int = 12) -> str:
    """
    Cheap deterministic summarizer (no LLM). Takes first/last lines, trims.
    """
    if not events:
        return "(empty)"

    lines = [normalize_newlines(e).strip() for e in events if normalize_newlines(e).strip()]
    if not lines:
        return "(empty)"

    if len(lines) <= max_lines:
        return "\n".join(lines)

    head_n = max_lines // 2
    tail_n = max_lines - head_n
    head = lines[:head_n]
    tail = lines[-tail_n:]
    return "\n".join(head + ["... (folded) ..."] + tail)
