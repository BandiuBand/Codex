# -*- coding: utf-8 -*-
from __future__ import annotations

from commands.base import BaseCommand
from core.types import CommandCall, DispatchResult, ExecutionContext
from core.memory import Memory
from utils.text import normalize_newlines


class FoldNowCommand(BaseCommand):
    @property
    def command_name(self) -> str:
        return "FOLD_NOW"

    def execute(self, memory: Memory, call: CommandCall, ctx: ExecutionContext) -> DispatchResult:
        reason = normalize_newlines(call.args.get("reason", "manual_fold")).strip() or "manual_fold"
        fold = memory.fold_now(reason=reason, keep_last_events=40)
        add_history = getattr(memory, "add_history", None)
        if fold:
            if callable(add_history):
                add_history(f"ASSISTANT: (fold created: replaced={fold.replaced_events})")
            else:
                memory.add_event("assistant", f"(fold created: replaced={fold.replaced_events})", kind="note")
        else:
            if callable(add_history):
                add_history("ASSISTANT: (fold skipped: not enough history)")
            else:
                memory.add_event("assistant", "(fold skipped: not enough history)", kind="note")
        return DispatchResult(
            memory=memory,
            user_message=None,
            stop_for_user_input=False,
            debug="fold_now",
        )
