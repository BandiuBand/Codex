# -*- coding: utf-8 -*-

from __future__ import annotations

from commands.base import BaseCommand
from commands.util import need
from core.types import CommandCall, DispatchResult, ExecutionContext
from core.memory import Memory


class FoldCommand(BaseCommand):
    def __init__(self) -> None:
        super().__init__(
            name="FOLD",
            prompt_help=(
                """FOLD: Create a fold once and replace the selected BODY range with a placeholder.

Required fields:
LABEL:
  short label (usually a short summary)
START:
  exact start substring (must exist in BODY)
END:
  exact end substring (must exist after START)

Optional fields:
ID:
  fold_id to use; if omitted the system generates one.

Example:
<CMD>
FOLD
LABEL:
Input specs
START:
Specs:
END:
0.5%
</CMD>
"""
            ),
        )

    def execute(self, memory: Memory, call: CommandCall, ctx: ExecutionContext) -> DispatchResult:
        label = need(call.payload, "LABEL")
        start = need(call.payload, "START")
        end = need(call.payload, "END")
        fold_id = call.payload.get("ID")
        new_id = memory.fold_range(start=start, end=end, label=label, fold_id=fold_id)
        if ctx.debug_log:
            ctx.debug_log(f"FOLD created/used id={new_id}")
        memory.add_history(memory.format_cmd_block(call))
        return DispatchResult(memory=memory)
