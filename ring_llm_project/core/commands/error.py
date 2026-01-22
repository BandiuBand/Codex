# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict

from core.commands.base import Command, CommandContext, CommandResult
from core.memory import Memory


class ErrorCommand(Command):
    def execute(self, args: Dict[str, str], memory: Memory, ctx: CommandContext) -> CommandResult:
        code = (args.get("code") or "ERROR").strip()
        msg = (args.get("message") or "").strip()
        memory.add_history(f"CMD ERROR code={code} message={msg}")
        memory.add_debug(f"LLM ERROR: {code} | {msg}")
        # stop to avoid infinite loops unless you prefer to continue
        return CommandResult(ok=False, stop=True, error=f"{code}:{msg}")
