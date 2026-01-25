# -*- coding: utf-8 -*-

from __future__ import annotations

from commands.base import BaseCommand
from commands.util import need
from core.types import CommandCall, DispatchResult, ExecutionContext
from core.memory import Memory


class SayCommand(BaseCommand):
    def __init__(self) -> None:
        super().__init__(
            name="SAY",
            prompt_help=(
                """SAY: Display text to the user.

Fields (choose one):
TEXT:
  ...text to show...
FOLD_ID:
  ...show content of this fold...
"""
            ),
        )

    def execute(self, memory: Memory, call: CommandCall, ctx: ExecutionContext) -> DispatchResult:
        text = call.payload.get("TEXT")
        if text is None:
            fold_id = need(call.payload, "FOLD_ID")
            f = memory.folds.get(fold_id)
            if f is None:
                text = f"[SAY] Unknown fold id: {fold_id}"
            else:
                text = f.content

        if ctx.io is not None:
            ctx.io.say(text)

        # Do not change body, only log history
        memory.add_history(memory.format_cmd_block(call))
        return DispatchResult(memory=memory)
