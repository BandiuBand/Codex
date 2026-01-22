# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Optional

from .fold import FoldedItem


def safe_one_line(s: str) -> str:
    s = (s or "").replace("\r\n", "\n").replace("\r", "\n")
    s = " ".join(x.strip() for x in s.split("\n") if x.strip())
    return s.strip()


@dataclass
class Memory:
    goal: str = ""

    vars: Dict[str, str] = field(default_factory=dict)

    plan_items: List[str] = field(default_factory=list)
    current_step: str = ""

    # INBOX: список (reply_id, text)
    inbox: List[Tuple[int, str]] = field(default_factory=list)

    history: List[str] = field(default_factory=list)
    debug: List[str] = field(default_factory=list)

    folded: Dict[int, FoldedItem] = field(default_factory=dict)

    next_reply_id: int = 1
    next_fold_id: int = 1

    pending_var: str = ""
    pending_question: str = ""

    # -----------------
    # Лог
    # -----------------

    def add_history(self, line: str) -> None:
        self.history.append(line)

    def add_debug(self, line: str) -> None:
        self.debug.append(line)

    # -----------------
    # INBOX
    # -----------------

    def push_reply(self, text: str) -> int:
        rid = self.next_reply_id
        self.next_reply_id += 1
        self.inbox.append((rid, text))
        self.add_history(f"USER_REPLY id={rid} text={safe_one_line(text)}")
        return rid

    def pop_reply_by_id(self, rid: int) -> Optional[str]:
        found_text: Optional[str] = None
        new_inbox: List[Tuple[int, str]] = []
        for x_id, x_text in self.inbox:
            if x_id == rid and found_text is None:
                found_text = x_text
            else:
                new_inbox.append((x_id, x_text))
        self.inbox = new_inbox
        return found_text

    # -----------------
    # Snapshot
    # -----------------

    def _render_vars(self) -> List[str]:
        if not self.vars:
            return ["(empty)"]
        out = []
        for k in sorted(self.vars.keys()):
            out.append(f"{k}={self.vars[k]}")
        return out

    def _render_plan(self) -> List[str]:
        if not self.plan_items:
            out = ["(empty)"]
        else:
            out = [f"{i}) {item}" for i, item in enumerate(self.plan_items, start=1)]
        if self.current_step:
            out.append(f"CURRENT: {self.current_step}")
        return out

    def _render_inbox(self) -> List[str]:
        if not self.inbox:
            return ["(empty)"]
        out = []
        for rid, text in self.inbox:
            out.append(f"USER_REPLY id={rid} text={safe_one_line(text)}")
        return out

    def _render_folded(self) -> List[str]:
        if not self.folded:
            return ["(none)"]
        out = []
        for fid in sorted(self.folded.keys()):
            it = self.folded[fid]
            out.append(f"id={fid} section={it.section} summary={it.summary}")
        return out

    def _body_for_fill(self) -> str:
        return "\n".join([
            self.goal or "",
            "\n".join(self._render_vars()),
            self.pending_var or "",
            self.pending_question or "",
            "\n".join(self._render_plan()),
            "\n".join(self._render_inbox()),
            "\n".join(self._render_folded()),
            "\n".join(self.history),
            "\n".join(self.debug),
        ])

    def estimate_fill_percent(self, max_context_chars: int) -> int:
        if max_context_chars <= 0:
            return 0
        pct = int(round(100.0 * len(self._body_for_fill()) / max_context_chars))
        return max(0, min(pct, 999))

    def snapshot(self, max_context_chars: int) -> str:
        fill = self.estimate_fill_percent(max_context_chars)

        lines: List[str] = []
        lines.append("===MEMORY===")
        lines.append(f"memory_fill={fill}%")
        lines.append("")
        lines.append("[GOAL]")
        lines.append(self.goal or "(empty)")
        lines.append("[/GOAL]")
        lines.append("")
        lines.append("[VARS]")
        lines.extend(self._render_vars())
        lines.append("[/VARS]")
        lines.append("")
        lines.append("[PENDING]")
        if self.pending_var:
            lines.append(f"pending_var={self.pending_var}")
            lines.append(f"pending_question={self.pending_question}")
        else:
            lines.append("(empty)")
        lines.append("[/PENDING]")
        lines.append("")
        lines.append("[PLAN]")
        lines.extend(self._render_plan())
        lines.append("[/PLAN]")
        lines.append("")
        lines.append("[INBOX]")
        lines.extend(self._render_inbox())
        lines.append("[/INBOX]")
        lines.append("")
        lines.append("[FOLDED]")
        lines.extend(self._render_folded())
        lines.append("[/FOLDED]")
        lines.append("")
        lines.append("[HISTORY]")
        lines.extend(self.history if self.history else ["(empty)"])
        lines.append("[/HISTORY]")
        lines.append("")
        lines.append("[DEBUG]")
        lines.extend(self.debug if self.debug else ["(empty)"])
        lines.append("[/DEBUG]")
        lines.append("===END_MEMORY===")
        return "\n".join(lines)

    # -----------------
    # Save / Load
    # -----------------

    def to_dict(self) -> dict:
        data = asdict(self)
        folded2 = {}
        for k, v in self.folded.items():
            folded2[str(k)] = asdict(v)
        data["folded"] = folded2
        return data

    @staticmethod
    def from_dict(data: dict) -> "Memory":
        m = Memory()
        m.goal = data.get("goal", "")
        m.vars = dict(data.get("vars", {}))
        m.plan_items = list(data.get("plan_items", []))
        m.current_step = data.get("current_step", "")
        m.inbox = [tuple(x) for x in data.get("inbox", [])]
        m.history = list(data.get("history", []))
        m.debug = list(data.get("debug", []))
        m.next_reply_id = int(data.get("next_reply_id", 1))
        m.next_fold_id = int(data.get("next_fold_id", 1))
        m.pending_var = data.get("pending_var", "") or ""
        m.pending_question = data.get("pending_question", "") or ""

        m.folded = {}
        folded2 = data.get("folded", {}) or {}
        for k, v in folded2.items():
            fid = int(k)
            m.folded[fid] = FoldedItem(
                fold_id=int(v.get("fold_id", fid)),
                section=v.get("section", ""),
                summary=v.get("summary", ""),
                original=v.get("original", ""),
                created_ts=float(v.get("created_ts", time.time())),
            )
        return m

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @staticmethod
    def load(path: str) -> Optional["Memory"]:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Memory.from_dict(data)
