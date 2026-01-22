# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict

from core.commands.base import Command, CommandContext, CommandResult
from core.memory import Memory
from utils.text import safe_int


class AskCommand(Command):
    def execute(self, args: Dict[str, str], memory: Memory, ctx: CommandContext) -> CommandResult:
        text = (args.get("text") or "").strip()
        wait = safe_int(args.get("wait", "0"), 0)

        if not text:
            memory.add_debug("ASK: empty text -> rejected")
            return CommandResult(ok=False, error="ASK_missing_text")

        # Anti-repeat: if same ASK text repeated too often recently, suppress it.
        recent = ctx.executed_recent_cmds[-ctx.repeat_ask_window :]
        same = [c for c in recent if c.startswith("ASK|") and c == f"ASK|{text}"]
        if len(same) >= ctx.repeat_ask_limit:
            memory.add_debug(f"ASK suppressed (repeated): {text}")
            memory.add_inbox(f"(suppressed repeated ASK) {text}")
            return CommandResult(ok=True, user_message=None, wait_user=False)

        memory.add_history(f"CMD ASK wait={wait} text={text}")
        return CommandResult(ok=True, user_message=text, wait_user=True)
