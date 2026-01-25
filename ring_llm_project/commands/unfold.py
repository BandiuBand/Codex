# -*- coding: utf-8 -*-

from __future__ import annotations

from commands.base import BaseCommand
from commands.util import need
from core.types import CommandCall, DispatchResult, ExecutionContext
from core.memory import Memory


class UnfoldCommand(BaseCommand):
    def __init__(self) -> None:
        super().__init__(
            name="UNFOLD",
            prompt_help=(
                """UNFOLD: Toggle a fold.

Fields:
ID:
  Fold id to toggle.

Behavior:
- If the fold is currently collapsed (placeholder exists in BODY) -> expands it.
- Else, if the fold content is currently expanded in BODY -> collapses it back.
"""
            ),
        )

    def execute(self, memory: Memory, call: CommandCall, ctx: ExecutionContext) -> DispatchResult:
        fold_id = need(call.payload, "ID")
        memory.toggle_fold(fold_id)
        memory.add_history(ctx.render_cmd_for_history(call))
        return DispatchResult(memory=memory)
