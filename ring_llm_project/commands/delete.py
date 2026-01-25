# -*- coding: utf-8 -*-

from __future__ import annotations

from commands.base import BaseCommand
from commands.util import need
from core.types import CommandCall, DispatchResult, ExecutionContext
from core.memory import Memory


class DeleteCommand(BaseCommand):
    def __init__(self) -> None:
        super().__init__(
            name="DELETE",
            prompt_help=(
                """DELETE: Deletes a range from the memory BODY.

Fields:
START:
  (exact substring found in BODY)
END:
  (exact substring found in BODY after START)

Effect:
- Deletes the inclusive range [START..END] from BODY.
- Service sections are never affected (command works on BODY only).
"""
            ),
        )

    def execute(self, memory: Memory, call: CommandCall, ctx: ExecutionContext) -> DispatchResult:
        start = need(call.payload, "START")
        end = need(call.payload, "END")
        memory.delete_range(start, end)
        memory.add_history(call)
        return DispatchResult(memory=memory)
