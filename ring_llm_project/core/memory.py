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
        line = normalize_newlines(line).strip()
        if not line:
            return
        self.history.append(line)
        if len(self.history) > self.history_max_events:
            # hard drop oldest (we also have optional auto-fold in orchestrator)
            self.history = self.history[-self.history_max_events :]

    def add_inbox(self, line: str) -> None:
        line = normalize_newlines(line).strip()
        if line:
            self.inbox.append(line)

    def add_debug(self, line: str) -> None:
        line = normalize_newlines(line).strip()
        if line:
            self.debug.append(line)

    def set_goal(self, text: str) -> None:
        self.goal = normalize_newlines(text).strip()

    def set_var(self, key: str, value: str) -> None:
        self.vars[str(key).strip()] = normalize_newlines(str(value)).strip()

    def set_plan(self, steps: List[str], current: str) -> None:
        self.plan_steps = [
            normalize_newlines(s).strip() for s in steps if normalize_newlines(s).strip()
        ]
        self.plan_current = normalize_newlines(current).strip()

    def memory_fill_percent(self) -> int:
        t = self.to_text(include_end_marker=False)
        if self.max_chars <= 0:
            return 0
        p = int(round(100 * (len(t) / self.max_chars)))
        if p < 0:
            p = 0
        if p > 100:
            p = 100
        return p

    def fingerprint(self) -> str:
        t = self.to_text(include_end_marker=False).encode("utf-8")
        return hashlib.sha256(t).hexdigest()[:16]

    def to_text(self, include_end_marker: bool = True) -> str:
        # keep stable order for vars
        vars_lines = []
        for k in sorted(self.vars.keys()):
            vars_lines.append(f"{k}={self.vars[k]}")

        plan_lines = []
        for i, s in enumerate(self.plan_steps, start=1):
            plan_lines.append(f"{i}) {s}")
        if self.plan_current:
            plan_lines.append(f"CURRENT: {self.plan_current}")

        inbox_text = "(empty)" if not self.inbox else "\n".join(self.inbox)
        folded_text = "(none)" if not self.folded else "\n".join(
            f.to_text() for f in self.folded
        )
        history_text = "(empty)" if not self.history else "\n".join(self.history)
        debug_text = "(empty)" if not self.debug else "\n".join(self.debug)

        out = []
        out.append("===MEMORY===")
        out.append(f"memory_fill={self.memory_fill_percent()}%")
        out.append("")
        out.append("[GOAL]")
        out.append(self.goal if self.goal else "(empty)")
        out.append("[/GOAL]")
        out.append("")
        out.append("[VARS]")
        out.append("\n".join(vars_lines) if vars_lines else "(empty)")
        out.append("[/VARS]")
        out.append("")
        out.append("[PLAN]")
        out.append("\n".join(plan_lines) if plan_lines else "(empty)")
        out.append("[/PLAN]")
        out.append("")
        out.append("[INBOX]")
        out.append(inbox_text)
        out.append("[/INBOX]")
        out.append("")
        out.append("[FOLDED]")
        out.append(folded_text)
        out.append("[/FOLDED]")
        out.append("")
        out.append("[HISTORY]")
        out.append(history_text)
        out.append("[/HISTORY]")
        out.append("")
        out.append("[DEBUG]")
        out.append(debug_text)
        out.append("[/DEBUG]")
        if include_end_marker:
            out.append("===END_MEMORY===")
        return "\n".join(out)

    def auto_fold_if_needed(self, keep_last_events: int) -> Optional[Fold]:
        """
        If memory text too long, fold older history into one Fold entry.
        """
        text_len = len(self.to_text(include_end_marker=False))
        if text_len <= self.max_chars:
            return None
        if len(self.history) <= keep_last_events:
            return None

        old = self.history[:-keep_last_events]
        new = self.history[-keep_last_events:]
        summary = naive_summarize_events(old, max_lines=12)

        fold = Fold(
            reason="auto_fold: memory too large",
            summary=summary,
            replaced_events=len(old),
        )
        self.folded.append(fold)
        self.history = new
        return fold
