from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ClipboardEntry:
    text: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FoldEntry:
    fold_id: str
    name: str
    content: str
    created_ts: str
    state: str = "folded"  # "folded" | "unfolded"
    access_log: List[Dict[str, Any]] = field(default_factory=list)

    def mark_access(self, event: Dict[str, Any]) -> None:
        self.access_log.append(event)


@dataclass
class Memory:
    """
    Canonical memory contract.
    Model-visible state is ONE string: `document`.
    """

    document: str = ""
    clipboard: ClipboardEntry = field(default_factory=ClipboardEntry)
    events: List[Dict[str, Any]] = field(default_factory=list)

    # Folds are NOT visible to model unless unfolded.
    folds: Dict[str, FoldEntry] = field(default_factory=dict)

    # --- Document API ---
    def get_document(self) -> str:
        return self.document

    def set_document(self, doc: str) -> None:
        if not isinstance(doc, str):
            raise TypeError("Memory.set_document: doc must be str")
        self.document = doc

    # --- Clipboard API ---
    def clipboard_get(self) -> Optional[str]:
        t = self.clipboard.text
        return t if isinstance(t, str) and t != "" else None

    def clipboard_set(self, text: str, meta: Dict[str, Any]) -> None:
        if not isinstance(text, str):
            raise TypeError("Memory.clipboard_set: text must be str")
        if not isinstance(meta, dict):
            raise TypeError("Memory.clipboard_set: meta must be dict")
        self.clipboard = ClipboardEntry(text=text, meta=meta)

    # --- Events API ---
    def add_event(self, event: Dict[str, Any]) -> None:
        if isinstance(event, dict):
            self.events.append(event)

    # --- Folds API ---
    def fold_put(self, fold_id: str, name: str, content: str) -> None:
        if not isinstance(fold_id, str) or not fold_id:
            raise TypeError("fold_id must be non-empty str")
        if not isinstance(name, str) or not name:
            raise TypeError("name must be non-empty str")
        if not isinstance(content, str):
            raise TypeError("content must be str")

        if fold_id in self.folds:
            # We do NOT silently overwrite: it's safer.
            raise ValueError(f"Fold '{fold_id}' already exists")

        self.folds[fold_id] = FoldEntry(
            fold_id=fold_id,
            name=name,
            content=content,
            created_ts=_now_utc_iso(),
            state="folded",
        )

    def fold_update_content(self, fold_id: str, new_content: str) -> None:
        f = self.fold_get(fold_id)
        if not isinstance(new_content, str):
            raise TypeError("new_content must be str")
        f.content = new_content

    def fold_get(self, fold_id: str) -> FoldEntry:
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
        """
        What model sees inside [FOLDED] block.
        Only currently folded entries are listed.
        """

        folded = [f for f in self.folds.values() if f.state == "folded"]
        if not folded:
            return "(none)"
        lines = []
        for f in folded:
            # minimal exposure: id + name only
            lines.append(f"- {f.fold_id} | {f.name}")
        return "\n".join(lines)

    def folds_sync_index_into_document(self) -> None:
        """
        Replace content between [FOLDED] and [/FOLDED] in `document`.
        If tags are absent, does nothing (you can enforce them in your template).
        """

        doc = self.get_document()
        a = doc.find("[FOLDED]")
        b = doc.find("[/FOLDED]")
        if a < 0 or b < 0 or b < a:
            return

        start = a + len("[FOLDED]")
        new_mid = "\n" + self.folds_render_index() + "\n"
        new_doc = doc[:start] + new_mid + doc[b:]
        self.set_document(new_doc)
