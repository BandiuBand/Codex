from __future__ import annotations

from typing import Any

from commands.base import BaseCommand
from core.types import CommandCall, DispatchResult, ExecutionContext


class LoopDoneCommand(BaseCommand):
    """
    <CMD>LOOP DONE</CMD>

    - НЕ змінює пам'ять
    - НЕ пишеться в історію/пам'ять (visible_event=False)
    - Служить лише як сигнал для LoopingStepSequence (loop_done=True)
    """
    @property
    def command_name(self) -> str:
        return "LOOP DONE"

    @property
    def prompt_help(self) -> str:
        # English-only
        return (
            "Command: <CMD>LOOP DONE</CMD>\n"
            "Purpose: stop the current internal loop. Output exactly this command when the loop should end.\n"
            "No arguments."
        )

    def execute(self, memory: Any, call: CommandCall, ctx: ExecutionContext) -> DispatchResult:
        return DispatchResult(
            memory=memory,
            loop_done=True,
            visible_event=False,
            user_output=None,
            debug_note="Loop termination signal."
        )
