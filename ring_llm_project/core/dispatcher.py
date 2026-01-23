# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from core.memory import Memory
from core.parser import ParsedCommand
from commands.registry import CommandRegistry
from utils.text import normalize_newlines


@dataclass
class DispatchResult:
    user_message: Optional[str] = None
    stop_for_user_input: bool = False  # e.g. ASK
    debug: str = ""


class CommandDispatcher:
    def __init__(self, registry: CommandRegistry):
        self.registry = registry

    def dispatch(self, memory: Memory, cmd: ParsedCommand) -> DispatchResult:
        handler = self.registry.get(cmd.name)
        if handler is None:
            memory.add_history(f"CMD_UNKNOWN {cmd.raw}")
            return DispatchResult(
                user_message=f"Невідома команда: {cmd.name}",
                stop_for_user_input=True,
                debug="unknown_command",
            )

        # log command line exactly
        memory.add_history(f"LLM -> {cmd.raw}")

        # execute
        result = handler.execute(memory, cmd.args)

        # handler may already add history/inbox etc.
        return result
