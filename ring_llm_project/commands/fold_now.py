# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict

from commands.base import BaseCommand
from core.types import DispatchResult
from core.memory import Memory
from utils.text import normalize_newlines


class FoldNowCommand(BaseCommand):
    name = "FOLD_NOW"

    def execute(self, memory: Memory, args: Dict[str, str]) -> DispatchResult:
        reason = normalize_newlines(args.get("reason", "manual_fold")).strip() or "manual_fold"
        fold = memory.fold_now(reason=reason, keep_last_events=40)
        if fold:
            memory.add_history(f"ASSISTANT: (fold created: replaced={fold.replaced_events})")
        else:
            memory.add_history("ASSISTANT: (fold skipped: not enough history)")
        return DispatchResult(user_message=None, stop_for_user_input=False, debug="fold_now")
