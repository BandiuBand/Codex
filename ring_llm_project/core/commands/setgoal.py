# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict

from core.commands.base import Command, CommandContext, CommandResult
from core.memory import Memory


class SetGoalCommand(Command):
    def execute(self, args: Dict[str, str], memory: Memory, ctx: CommandContext) -> CommandResult:
        text = (args.get("text") or "").strip()
        if not text:
            return CommandResult(ok=False, error="SETGOAL_missing_text")
        memory.set_goal(text)
        memory.add_history(f"CMD SETGOAL text={text}")
        return CommandResult(ok=True)
