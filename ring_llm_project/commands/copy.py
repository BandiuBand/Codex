# -*- coding: utf-8 -*-

from __future__ import annotations

from commands.base import BaseCommand
from commands.util import need
from core.types import CommandCall, DispatchResult, ExecutionContext
from core.memory import Memory


class CopyCommand(BaseCommand):
    def __init__(self) -> None:
        super().__init__(
            name="COPY",
            prompt_help=(
                "COPY: Copies a selected fragment from MEMORY BODY into CLIPBOARD.\n"
                "Provide exact START and END substrings that appear in the MEMORY BODY.\n\n"
                "Format:\n"
                "<CMD>\nCOPY\nSTART:\n...\nEND:\n...\n</CMD>\n"
            ),
        )

    def execute(self, memory: Memory, call: CommandCall, ctx: ExecutionContext) -> DispatchResult:
        start = need(call.payload, "START")
        end = need(call.payload, "END")
        frag = memory.copy_body_range_to_clipboard(start, end)
        if ctx.debug_commands:
            ctx.log(f"[COPY] {len(frag)} chars")
        return DispatchResult(memory=memory)
