# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .memory import Memory


@dataclass
class PolicyValidator:
    memory_fold_threshold_percent: int
    max_context_chars: int

    def validate(self, mem: Memory, cmd: str, kv: Dict[str, str]) -> Optional[str]:
        fill = mem.estimate_fill_percent(self.max_context_chars)

        # 1) INBOX не порожній -> тільки FOLD_REPLY
        if mem.inbox:
            if cmd != "FOLD_REPLY":
                return "INBOX не порожній: дозволено лише CMD FOLD_REPLY."
            return None

        # 2) pending_var -> заборонити ASK
        if mem.pending_var and cmd == "ASK":
            return f"PENDING встановлено ({mem.pending_var}): заборонено ASK поки не буде FOLD_REPLY."

        # 3) ASK правила
        if cmd == "ASK":
            if kv.get("wait", "").strip() != "1":
                return "ASK має бути wait=1 (blocking)."
            if not kv.get("var", "").strip():
                return "ASK має містити var=<name>."
            if not kv.get("text", "").strip():
                return "ASK має містити text=<question>."

        # 4) якщо memory_fill великий -> вимагати fold/delete
        if fill > self.memory_fold_threshold_percent:
            if cmd not in ("FOLD_SECTION", "DELETE_SECTION"):
                return f"memory_fill={fill}% > {self.memory_fold_threshold_percent}%: очікується CMD FOLD_SECTION або CMD DELETE_SECTION."

        return None
