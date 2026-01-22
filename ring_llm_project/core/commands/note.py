# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict

from core.commands.base import Command, CommandContext, CommandResult
from core.memory import Memory


class NoteCommand(Command):
    def execute(self, args: Dict[str, str], memory: Memory, ctx: CommandContext) -> CommandResult:
        text = (args.get("text") or "").strip()
        level = (args.get("level") or "debug").strip().lower()

        if not text:
            return CommandResult(ok=False, error="NOTE_missing_text")

        if level == "inbox":
            memory.add_inbox(text)
        else:
            memory.add_debug(text)

        memory.add_history(f"CMD NOTE level={level} text={text}")
        return CommandResult(ok=True)
