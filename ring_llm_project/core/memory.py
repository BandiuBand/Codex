# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


MEM_START = "===MEMORY==="
MEM_END = "===END_MEMORY==="


def _now_ts() -> int:
    return int(time.time())


@dataclass
class Fold:
    fold_id: str
    label: str
    content: str
    created_ts: int
    parent_fold_id: Optional[str] = None

    def placeholder(self) -> str:
        # Visible to the LLM; stable reference.
        return f"[[FOLD:{self.fold_id}|{self.label}]]"


class Memory:
    """Holds both service sections and the editable body.

    Service sections (NOT foldable/editable by edit commands):
      - [STATE]
      - [HISTORY]
      - [CLIPBOARD]
      - Memory markers lines

    Body is the text strictly between MEM_START and MEM_END.
    All folding/editing commands operate ONLY on the body.
    """

    def __init__(self, *, history_limit: int = 20, body: str = ""):
        self.state: Dict[str, str] = {}
        self.history: List[str] = []
        self.history_limit = history_limit
        self.clipboard: str = ""
        self.body: str = body
        self.folds: Dict[str, Fold] = {}
        self.current_fold_id: Optional[str] = None

    # ----------------------------
    # Serialization
    # ----------------------------

    def to_text(self) -> str:
        lines: List[str] = []

        # [STATE]
        lines.append("[STATE]")
        # Fill % only reflects body length (rough), not full text.
        fill = self.memory_fill_percent()
        lines.append(f"memory_fill={fill}%")
        if self.current_fold_id:
            lines.append(f"current_fold={self.current_fold_id}")
        for k, v in self.state.items():
            lines.append(f"{k}={v}")
        lines.append("")

        # [HISTORY]
        lines.append("[HISTORY]")
        for h in self.history[-self.history_limit :]:
            lines.append(h.rstrip("\n"))
        lines.append("")

        # [CLIPBOARD]
        lines.append("[CLIPBOARD]")
        lines.append(self.clipboard.rstrip("\n"))
        lines.append("")

        # Body
        lines.append(MEM_START)
        body = self.body.rstrip("\n")
        lines.append(body)
        lines.append(MEM_END)

        return "\n".join(lines).rstrip("\n") + "\n"

    def body_text(self) -> str:
        return self.body

    def set_body_text(self, text: str) -> None:
        self.body = text

    def memory_fill_percent(self, *, max_chars: int = 20000) -> int:
        n = len(self.body)
        return min(100, int((n / max_chars) * 100)) if max_chars > 0 else 0

    # ----------------------------
    # History / clipboard helpers
    # ----------------------------

    def push_history(self, cmd_block: str) -> None:
        self.history.append(cmd_block.rstrip("\n"))
        if len(self.history) > max(self.history_limit * 3, 100):
            # prevent unbounded growth
            self.history = self.history[-max(self.history_limit * 3, 100) :]

    def set_clipboard(self, text: str) -> None:
        self.clipboard = text

    # ----------------------------
    # Body editing helpers
    # ----------------------------

    def find_range(self, start: str, end: str) -> Tuple[int, int]:
        """Return (i_start, i_end_exclusive) for the first occurrence.

        Range is INCLUSIVE of the end token.
        """
        if not start or not end:
            raise ValueError("start/end cannot be empty")
        body = self.body
        i = body.find(start)
        if i < 0:
            raise ValueError("start token not found in body")
        j = body.find(end, i + len(start))
        if j < 0:
            raise ValueError("end token not found in body after start")
        j2 = j + len(end)
        return i, j2

    def extract_range(self, start: str, end: str) -> str:
        i, j = self.find_range(start, end)
        return self.body[i:j]

    def delete_range(self, start: str, end: str) -> None:
        i, j = self.find_range(start, end)
        self.body = self.body[:i] + self.body[j:]

    def insert_between(self, start: str, end: str, text: str, *, position: str = "after_start") -> None:
        """Insert text either after start token or before end token, but only if end occurs after start."""
        i, j = self.find_range(start, end)
        if position == "after_start":
            at = i + len(start)
        elif position == "before_end":
            at = j - len(end)
        else:
            raise ValueError("position must be after_start or before_end")
        self.body = self.body[:at] + text + self.body[at:]

    # ----------------------------
    # Folding
    # ----------------------------

    def _make_fold_id(self, label: str, content: str) -> str:
        h = hashlib.sha256()
        h.update(label.encode("utf-8"))
        h.update(b"\n")
        h.update(content.encode("utf-8"))
        h.update(str(_now_ts()).encode("ascii"))
        return h.hexdigest()[:16]

    def fold_by_range(self, start: str, end: str, label: str, fold_id: Optional[str] = None) -> str:
        content = self.extract_range(start, end)
        if fold_id is None:
            fold_id = self._make_fold_id(label, content)
        if fold_id in self.folds:
            # fold already exists: do NOT recreate; just try to refold if content currently present
            self.refold(fold_id)
            return fold_id

        fold = Fold(fold_id=fold_id, label=label, content=content, created_ts=_now_ts(), parent_fold_id=self.current_fold_id)
        self.folds[fold_id] = fold
        # Replace the extracted content with placeholder
        i, j = self.find_range(start, end)
        self.body = self.body[:i] + fold.placeholder() + self.body[j:]
        return fold_id

    def unfold(self, fold_id: str) -> None:
        fold = self.folds.get(fold_id)
        if not fold:
            raise ValueError(f"unknown fold_id: {fold_id}")
        ph = fold.placeholder()
        if ph not in self.body:
            # already unfolded or not in this body
            return
        self.body = self.body.replace(ph, fold.content, 1)

    def refold(self, fold_id: str) -> None:
        """Fold back a fold that was previously unfolded (replace exact content by placeholder)."""
        fold = self.folds.get(fold_id)
        if not fold:
            raise ValueError(f"unknown fold_id: {fold_id}")
        ph = fold.placeholder()
        if ph in self.body:
            return
        if fold.content not in self.body:
            raise ValueError("cannot refold: content not found in current body")
        self.body = self.body.replace(fold.content, ph, 1)

