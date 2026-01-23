# -*- coding: utf-8 -*-
from __future__ import annotations

from core.memory import Memory
from core.parser import ParsedCommand
from core.types import DispatchResult
from commands.registry import CommandRegistry


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
        return result
