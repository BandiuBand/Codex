# -*- coding: utf-8 -*-

from __future__ import annotations

from commands.base import BaseCommand
from commands.util import need
from core.types import CommandCall, DispatchResult, ExecutionContext
from core.memory import Memory


class CutCommand(BaseCommand):
    def __init__(self) -> None:
        super().__init__(
            name="CUT",
            prompt_help=(
                """CUT: Copies a range from the memory BODY into CLIPBOARD, then deletes it.

Fields:
START:
  (exact substring in BODY)
END:
  (exact substring in BODY after START)

Effect:
- CLIPBOARD is always overwritten.
- Range [START..END] is removed from BODY.
"""
            ),
        )

    def execute(self, memory: Memory, call: CommandCall, ctx: ExecutionContext) -> DispatchResult:
        start = need(call.payload, "START")
        end = need(call.payload, "END")
        copied = memory.copy_range(start, end)
        memory.clipboard = copied
        memory.delete_range(start, end)
        memory.add_history(call)
        return DispatchResult(memory=memory)
