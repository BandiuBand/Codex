# -*- coding: utf-8 -*-

from __future__ import annotations

from commands.base import BaseCommand
from commands.util import need
from core.types import CommandCall, DispatchResult, ExecutionContext
from core.memory import Memory


class InsertCommand(BaseCommand):
    def __init__(self) -> None:
        super().__init__(
            name="INSERT",
            prompt_help=(
                """INSERT: Inserts TEXT into the memory BODY after the first occurrence of START,
while also requiring that END occurs after START (to disambiguate).

Fields:
START:
  (exact substring that already exists in BODY)
END:
  (exact substring that already exists in BODY after START)
TEXT:
  (text to insert; can be multi-line)

Effect:
- Finds START in BODY.
- Ensures END exists after START.
- Inserts TEXT right after START.
"""
            ),
        )

    def execute(self, memory: Memory, call: CommandCall, ctx: ExecutionContext) -> DispatchResult:
        start = need(call.payload, "START")
        end = need(call.payload, "END")
        text = need(call.payload, "TEXT")

        memory.insert_after_with_guard(start, end, text)
        memory.add_history(call)
        return DispatchResult(memory=memory)
