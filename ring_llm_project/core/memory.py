from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import time
import hashlib


def _now_ts() -> float:
    return time.time()


def _fp(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]


@dataclass
class LinkMeta:
    created_ts: float
    parent_fold_id: Optional[str]
    appearances: List[Dict[str, str]] = field(default_factory=list)
    # appearances items: {"ts": "...", "fold_id": "...", "reason": "..."} or {"ts": "...", "root": "1"}

    def add_appearance(self, fold_id: Optional[str], reason: str) -> None:
        item = {"ts": str(_now_ts()), "reason": reason}
        if fold_id is None:
            item["root"] = "1"
        else:
            item["fold_id"] = fold_id
        self.appearances.append(item)


@dataclass
class Link:
    id: str
    text: str
    meta: LinkMeta


@dataclass
class Fold:
    id: str
    created_ts: float
    parent_fold_id: Optional[str]
    title: str
    content: str
    meta: Dict[str, str] = field(default_factory=dict)


@dataclass
class MemoryEvent:
    role: str  # "user" | "assistant" | "system"
    text: str
    ts: float = field(default_factory=_now_ts)
    related_fold_id: Optional[str] = None
    kind: str = "msg"  # "msg" | "ask" | "answer" | "note"


@dataclass
class Memory:
    goal: str = ""
    vars: Dict[str, str] = field(default_factory=dict)
    plan: List[str] = field(default_factory=list)

    history: List[MemoryEvent] = field(default_factory=list)
    folds: Dict[str, Fold] = field(default_factory=dict)
    links: Dict[str, Link] = field(default_factory=dict)

    max_chars: int = 30_000  # budget for prompt text, rough

    def add_event(self, role: str, text: str, kind: str = "msg", related_fold_id: Optional[str] = None) -> None:
        self.history.append(MemoryEvent(role=role, text=text, kind=kind, related_fold_id=related_fold_id))

    def create_fold(self, title: str, content: str, parent_fold_id: Optional[str] = None) -> Fold:
        fid = _fp(f"{title}\n{content}\n{_now_ts()}")
        fold = Fold(id=fid, created_ts=_now_ts(), parent_fold_id=parent_fold_id, title=title, content=content)
        self.folds[fid] = fold
        return fold

    def create_link(self, text: str, parent_fold_id: Optional[str] = None) -> Link:
        lid = _fp(f"LINK\n{text}\n{_now_ts()}")
        meta = LinkMeta(created_ts=_now_ts(), parent_fold_id=parent_fold_id)
        link = Link(id=lid, text=text, meta=meta)
        self.links[lid] = link
        return link

    def memory_fill_percent(self) -> int:
        # IMPORTANT: no recursion! Use internal computed length only.
        used = len(self.to_text(include_fill_line=False, include_end_marker=False))
        return int(min(100, (used / max(1, self.max_chars)) * 100))

    def to_text(self, include_fill_line: bool = True, include_end_marker: bool = True) -> str:
        out: List[str] = []
        if include_fill_line:
            out.append(f"[MEMORY fill={self.memory_fill_percent()}%]")
        out.append("[GOAL]")
        out.append(self.goal.strip() if self.goal else "(empty)")
        out.append("[/GOAL]\n")

        out.append("[VARS]")
        if self.vars:
            for k, v in self.vars.items():
                out.append(f"{k}={v}")
        else:
            out.append("(empty)")
        out.append("[/VARS]\n")

        out.append("[PLAN]")
        if self.plan:
            for i, p in enumerate(self.plan, 1):
                out.append(f"{i}) {p}")
        else:
            out.append("(empty)")
        out.append("[/PLAN]\n")

        out.append("[HISTORY]")
        if self.history:
            for ev in self.history[-200:]:
                # keep last N
                out.append(f"{int(ev.ts)} {ev.role.upper()} ({ev.kind}): {ev.text}")
        else:
            out.append("(empty)")
        out.append("[/HISTORY]\n")

        out.append("[FOLDS]")
        if self.folds:
            # show only meta; content is referenced by id to avoid prompt blow-up
            for fid, f in list(self.folds.items())[-50:]:
                out.append(f"- {fid} | {f.title} | parent={f.parent_fold_id or '-'} | ts={int(f.created_ts)}")
        else:
            out.append("(none)")
        out.append("[/FOLDS]")

        if include_end_marker:
            out.append("===END_MEMORY===")
        return "\n".join(out)
