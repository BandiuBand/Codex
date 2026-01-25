from __future__ import annotations
from typing import Optional
from .memory import Memory


class Folder:
    def __init__(self, keep_last_events: int = 30):
        self.keep_last_events = keep_last_events

    def auto_fold_if_needed(self, mem: Memory) -> Optional[str]:
        text = mem.to_text(include_fill_line=False)
        if len(text) <= mem.max_chars:
            return None

        # fold old history into one fold
        if len(mem.history) <= self.keep_last_events:
            return None

        old = mem.history[:-self.keep_last_events]
        keep = mem.history[-self.keep_last_events:]

        folded_text = "\n".join(f"{int(e.ts)} {e.role.upper()}({e.kind}): {e.text}" for e in old)
        fold = mem.create_fold(title="Auto-folded history", content=folded_text, parent_fold_id=None)

        mem.history = keep
        mem.add_event("system", f"Folded {len(old)} events into fold {fold.id}", kind="note", related_fold_id=fold.id)
        return fold.id
