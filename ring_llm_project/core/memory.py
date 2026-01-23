# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.fold import Fold, naive_summarize_events
from utils.text import normalize_newlines


@dataclass
class Memory:
    goal: str = ""
    vars: Dict[str, str] = field(default_factory=dict)
    plan_steps: List[str] = field(default_factory=list)
    plan_current: str = ""
    inbox: List[str] = field(default_factory=list)
    folded: List[Fold] = field(default_factory=list)
    history: List[str] = field(default_factory=list)
    debug: List[str] = field(default_factory=list)

    max_chars: int = 14000
    history_max_events: int = 200

    def add_history(self, line: str) -> None:
        line = normalize_newlines(line).rstrip()
        if not line.strip():
            return
        self.history.append(line)
        if len(self.history) > self.history_max_events:
            self.history = self.history[-self.history_max_events :]

    def add_inbox(self, line: str) -> None:
        line = normalize_newlines(line).rstrip()
        if line.strip():
            self.inbox.append(line)

    def add_debug(self, line: str) -> None:
        line = normalize_newlines(line).rstrip()
        if line.strip():
            self.debug.append(line)

    def set_goal(self, text: str) -> None:
        self.goal = normalize_newlines(text).strip()

    def set_var(self, key: str, value: str) -> None:
        self.vars[str(key).strip()] = normalize_newlines(str(value)).strip()

    def fingerprint(self) -> str:
        t = self._render(include_end_marker=False, include_fill_line=False).encode("utf-8")
        return hashlib.sha256(t).hexdigest()[:16]

    def memory_fill_percent(self) -> int:
        base = self._render(include_end_marker=False, include_fill_line=False)
        if self.max_chars <= 0:
            return 0
        p = int(round(100 * (len(base) / self.max_chars)))
        return 0 if p < 0 else (100 if p > 100 else p)

    def to_text(self, include_end_marker: bool = True) -> str:
        return self._render(include_end_marker=include_end_marker, include_fill_line=True)

    def _render(self, include_end_marker: bool, include_fill_line: bool) -> str:
        vars_lines = [f"{k}={self.vars[k]}" for k in sorted(self.vars.keys())]

        plan_lines: List[str] = []
        for i, s in enumerate(self.plan_steps, start=1):
            ss = normalize_newlines(s).strip()
            if ss:
                plan_lines.append(f"{i}) {ss}")
        if self.plan_current:
            plan_lines.append(f"CURRENT: {normalize_newlines(self.plan_current).strip()}")

        inbox_text = "(empty)" if not self.inbox else "\n".join(self.inbox)
        folded_text = "(none)" if not self.folded else "\n".join(f.to_text() for f in self.folded)
        history_text = "(empty)" if not self.history else "\n".join(self.history)
        debug_text = "(empty)" if not self.debug else "\n".join(self.debug)

        out: List[str] = []
        out.append("===MEMORY===")
        if include_fill_line:
            base_no_fill = self._render(include_end_marker=False, include_fill_line=False)
            if self.max_chars <= 0:
                fill = 0
            else:
                fill = int(round(100 * (len(base_no_fill) / self.max_chars)))
                fill = 0 if fill < 0 else (100 if fill > 100 else fill)
            out.append(f"memory_fill={fill}%")
            out.append("")  # keep readability

        out.append("[GOAL]")
        out.append(self.goal if self.goal else "(empty)")
        out.append("[/GOAL]\n")

        out.append("[VARS]")
        out.append("\n".join(vars_lines) if vars_lines else "(empty)")
        out.append("[/VARS]\n")

        out.append("[PLAN]")
        out.append("\n".join(plan_lines) if plan_lines else "(empty)")
        out.append("[/PLAN]\n")

        out.append("[INBOX]")
        out.append(inbox_text)
        out.append("[/INBOX]\n")

        out.append("[FOLDED]")
        out.append(folded_text)
        out.append("[/FOLDED]\n")

        out.append("[HISTORY]")
        out.append(history_text)
        out.append("[/HISTORY]\n")

        out.append("[DEBUG]")
        out.append(debug_text)
        out.append("[/DEBUG]")

        if include_end_marker:
            out.append("===END_MEMORY===")

        return "\n".join(out)

    def auto_fold_if_needed(self, keep_last_events: int) -> Optional[Fold]:
        text_len = len(self._render(include_end_marker=False, include_fill_line=False))
        if text_len <= self.max_chars:
            return None
        if len(self.history) <= keep_last_events:
            return None

        old = self.history[:-keep_last_events]
        new = self.history[-keep_last_events:]
        summary = naive_summarize_events(old, max_lines=12)

        fold = Fold.create(
            reason="auto_fold: memory too large",
            summary=summary,
            replaced_events=len(old),
        )
        self.folded.append(fold)
        self.history = new
        return fold

    def fold_now(self, reason: str, keep_last_events: int) -> Optional[Fold]:
        if len(self.history) <= keep_last_events:
            return None
        old = self.history[:-keep_last_events]
        new = self.history[-keep_last_events:]
        summary = naive_summarize_events(old, max_lines=12)

        fold = Fold.create(reason=reason, summary=summary, replaced_events=len(old))
        self.folded.append(fold)
        self.history = new
        return fold
