# -*- coding: utf-8 -*-

from __future__ import annotations

from commands.base import BaseCommand
from core.types import CommandCall, DispatchResult, ExecutionContext
from core.memory import Memory


class LoopDoneCommand(BaseCommand):
    def __init__(self) -> None:
        super().__init__(
            name="LOOP DONE",
            prompt_help=(
                """LOOP DONE: Exits the current StepLoop.

No fields.
"""
            ),
        )

    def execute(self, memory: Memory, call: CommandCall, ctx: ExecutionContext) -> DispatchResult:
        # not logged; loop wrapper may decide
        return DispatchResult(memory=memory, break_loop=True)
