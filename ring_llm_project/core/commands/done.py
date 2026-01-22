# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict

from core.commands.base import Command, CommandContext, CommandResult
from core.memory import Memory


class DoneCommand(Command):
    def execute(self, args: Dict[str, str], memory: Memory, ctx: CommandContext) -> CommandResult:
        text = (args.get("text") or "").strip()
        if text:
            memory.add_history(f"CMD DONE text={text}")
        else:
            memory.add_history("CMD DONE")
        return CommandResult(ok=True, stop=True)
