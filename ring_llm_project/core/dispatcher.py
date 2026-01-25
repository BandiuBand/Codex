# -*- coding: utf-8 -*-
from __future__ import annotations

from core.memory import Memory
from core.parser import ParsedCommand
from core.types import CommandCall, DispatchResult, ExecutionContext
from commands.base import BaseCommand
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
        if isinstance(handler, BaseCommand):
            call = CommandCall(raw=cmd.raw, name=cmd.name, args=cmd.args)
            return handler.execute(memory, call, ExecutionContext())
        if hasattr(handler, "execute"):
            return handler.execute(memory, cmd.args)
        return DispatchResult(
            memory=memory,
            user_message=f"Команда {cmd.name} не підтримується",
            stop_for_user_input=True,
            debug="unsupported_command",
        )
