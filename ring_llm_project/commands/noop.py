# -*- coding: utf-8 -*-
from __future__ import annotations

from commands.base import BaseCommand
from core.types import CommandCall, DispatchResult, ExecutionContext
from core.memory import Memory


class NoopCommand(BaseCommand):
    @property
    def command_name(self) -> str:
        return "NOOP"

    def execute(self, memory: Memory, call: CommandCall, ctx: ExecutionContext) -> DispatchResult:
        add_history = getattr(memory, "add_history", None)
        if callable(add_history):
            add_history("ASSISTANT: (noop)")
        else:
            memory.add_event("assistant", "(noop)", kind="note")
        return DispatchResult(
            memory=memory,
            user_message=None,
            stop_for_user_input=False,
            debug="noop",
        )
