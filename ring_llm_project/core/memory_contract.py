from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ClipboardEntry:
    text: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Memory:
    """
    Canonical memory contract for the whole project.
    Model-visible state is stored as ONE string: `document`.
    Commands and steps must ONLY use methods below, not internal fields.
    """
    document: str = ""
    clipboard: ClipboardEntry = field(default_factory=ClipboardEntry)
    events: List[Dict[str, Any]] = field(default_factory=list)

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
