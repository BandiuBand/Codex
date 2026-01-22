# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict

from core.commands.base import Command, CommandContext, CommandResult
from core.memory import Memory


class SetVarCommand(Command):
    def execute(self, args: Dict[str, str], memory: Memory, ctx: CommandContext) -> CommandResult:
        key = (args.get("key") or "").strip()
        value = (args.get("value") or "").strip()
        if not key:
            return CommandResult(ok=False, error="SETVAR_missing_key")
        memory.set_var(key, value)
        memory.add_history(f"CMD SETVAR key={key} value={value}")
        return CommandResult(ok=True)
