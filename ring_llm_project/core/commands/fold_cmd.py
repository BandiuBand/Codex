# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict

from core.commands.base import Command, CommandContext, CommandResult
from core.fold import Fold, naive_summarize_events
from core.memory import Memory
from utils.text import safe_int


class FoldCommand(Command):
    def execute(self, args: Dict[str, str], memory: Memory, ctx: CommandContext) -> CommandResult:
        reason = (args.get("reason") or "manual_fold").strip()
        keep_last = safe_int(args.get("keep_last", "30"), 30)

        if len(memory.history) <= keep_last:
            memory.add_debug("FOLD skipped: not enough history")
            return CommandResult(ok=True, folded_created=False)

        old = memory.history[:-keep_last]
        new = memory.history[-keep_last:]
        summary = naive_summarize_events(old, max_lines=12)

        fold = Fold(reason=reason, summary=summary, replaced_events=len(old))
        memory.folded.append(fold)
        memory.history = new
        memory.add_history(f"CMD FOLD reason={reason} keep_last={keep_last}")

        return CommandResult(ok=True, folded_created=True)
