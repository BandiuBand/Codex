from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
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
class ClipboardEntry:
    text: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Fold:
    id: str
    created_ts: float
    parent_fold_id: Optional[str]
    title: str
    content: str
    meta: Dict[str, str] = field(default_factory=dict)
    state: str = "folded"  # "folded" | "unfolded"
    appearances: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def fold_id(self) -> str:
        return self.id

    @property
    def name(self) -> str:
        return self.title

    def add_appearance(self, fold_id: Optional[str], reason: str) -> None:
        item: Dict[str, Any] = {"ts": str(_now_ts()), "reason": reason}
        if fold_id is None:
            item["root"] = "1"
        else:
            item["fold_id"] = fold_id
        self.appearances.append(item)

    def mark_access(self, event: Dict[str, Any]) -> None:
        self.appearances.append(event)


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

    document: str = ""
    clipboard: ClipboardEntry = field(default_factory=ClipboardEntry)
    events: List[Dict[str, Any]] = field(default_factory=list)

    history: List[MemoryEvent] = field(default_factory=list)
    folds: Dict[str, Fold] = field(default_factory=dict)
    links: Dict[str, Link] = field(default_factory=dict)

    max_chars: int = 30_000  # budget for prompt text, rough

    def add_event(
        self,
        role: str | Dict[str, Any],
        text: Optional[str] = None,
        kind: str = "msg",
        related_fold_id: Optional[str] = None,
    ) -> None:
        if isinstance(role, dict) and text is None:
            self.events.append(role)
            return
        if not isinstance(role, str) or not isinstance(text, str):
            raise TypeError("Memory.add_event: role and text must be str")
        self.history.append(MemoryEvent(role=role, text=text, kind=kind, related_fold_id=related_fold_id))

    def get_document(self) -> str:
        return self.document

    def set_document(self, doc: str) -> None:
        if not isinstance(doc, str):
            raise TypeError("Memory.set_document: doc must be str")
        self.document = doc

    def clipboard_get(self) -> Optional[str]:
        t = self.clipboard.text
        return t if isinstance(t, str) and t != "" else None

    def clipboard_set(self, text: str, meta: Dict[str, Any]) -> None:
        if not isinstance(text, str):
            raise TypeError("Memory.clipboard_set: text must be str")
        if not isinstance(meta, dict):
            raise TypeError("Memory.clipboard_set: meta must be dict")
        self.clipboard = ClipboardEntry(text=text, meta=meta)

    def create_fold(self, title: str, content: str, parent_fold_id: Optional[str] = None) -> Fold:
        fid = _fp(f"{title}\n{content}\n{_now_ts()}")
        fold = Fold(id=fid, created_ts=_now_ts(), parent_fold_id=parent_fold_id, title=title, content=content)
        fold.add_appearance(parent_fold_id, "create")
        self.folds[fid] = fold
        return fold

    def create_link(self, text: str, parent_fold_id: Optional[str] = None) -> Link:
        lid = _fp(f"LINK\n{text}\n{_now_ts()}")
        meta = LinkMeta(created_ts=_now_ts(), parent_fold_id=parent_fold_id)
        link = Link(id=lid, text=text, meta=meta)
        self.links[lid] = link
        return link

    def fold_put(self, fold_id: str, name: str, content: str) -> None:
        if not isinstance(fold_id, str) or not fold_id:
            raise TypeError("fold_id must be non-empty str")
        if not isinstance(name, str) or not name:
            raise TypeError("name must be non-empty str")
        if not isinstance(content, str):
            raise TypeError("content must be str")

        if fold_id in self.folds:
            raise ValueError(f"Fold '{fold_id}' already exists")

        fold = Fold(
            id=fold_id,
            created_ts=_now_ts(),
            parent_fold_id=None,
            title=name,
            content=content,
            state="folded",
        )
        fold.add_appearance(None, "create")
        self.folds[fold_id] = fold

    def fold_update_content(self, fold_id: str, new_content: str) -> None:
        f = self.fold_get(fold_id)
        if not isinstance(new_content, str):
            raise TypeError("new_content must be str")
        f.content = new_content

    def fold_get(self, fold_id: str) -> Fold:
        f = self.folds.get(fold_id)
        if f is None:
            raise KeyError(f"Fold '{fold_id}' not found")
        return f

    def fold_set_state(self, fold_id: str, state: str) -> None:
        f = self.fold_get(fold_id)
        if state not in ("folded", "unfolded"):
            raise ValueError("state must be 'folded' or 'unfolded'")
        f.state = state

    def folds_render_index(self) -> str:
        folded = [f for f in self.folds.values() if f.state == "folded"]
        if not folded:
            return "(none)"
        lines = []
        for f in folded:
            lines.append(f"- {f.id} | {f.title}")
        return "\n".join(lines)

    def folds_sync_index_into_document(self) -> None:
        doc = self.get_document()
        a = doc.find("[FOLDED]")
        b = doc.find("[/FOLDED]")
        if a < 0 or b < 0 or b < a:
            return

        start = a + len("[FOLDED]")
        new_mid = "\n" + self.folds_render_index() + "\n"
        new_doc = doc[:start] + new_mid + doc[b:]
        self.set_document(new_doc)

    def memory_fill_percent(self) -> int:
        # IMPORTANT: no recursion! Use internal computed length only.
        used = len(self.to_text(include_fill_line=False))
        return int(min(100, (used / max(1, self.max_chars)) * 100))

    def to_text(self, include_fill_line: bool = True) -> str:
        out: List[str] = []
        out.append("[STATE]")
        if include_fill_line:
            out.append(f"memory_fill={self.memory_fill_percent()}%")
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

        out.append("[FOLDS]")
        if self.folds:
            # show only meta; content is referenced by id to avoid prompt blow-up
            for fid, f in list(self.folds.items())[-50:]:
                out.append(f"- {fid} | {f.title} | parent={f.parent_fold_id or '-'} | ts={int(f.created_ts)}")
        else:
            out.append("(none)")
        out.append("[/FOLDS]")
        out.append("[/STATE]\n")

        out.append("[HISTORY]")
        if self.history:
            for ev in self.history[-200:]:
                # keep last N
                out.append(f"{int(ev.ts)} {ev.role.upper()} ({ev.kind}): {ev.text}")
        else:
            out.append("(empty)")
        out.append("[/HISTORY]\n")

        out.append("[CLIPBOARD]")
        clipboard_text = self.clipboard.text if isinstance(self.clipboard.text, str) else ""
        clipboard_meta = self.clipboard.meta if isinstance(self.clipboard.meta, dict) else {}
        if not clipboard_text and not clipboard_meta:
            out.append("(empty)")
        else:
            if clipboard_text:
                out.append(clipboard_text)
            for k, v in clipboard_meta.items():
                out.append(f"meta.{k}={v}")
        out.append("[/CLIPBOARD]\n")

        out.append("===MEMORY===")
        body = self.document if isinstance(self.document, str) and self.document else "(empty)"
        out.append(body)
        out.append("===END_MEMORY===")
        return "\n".join(out)
