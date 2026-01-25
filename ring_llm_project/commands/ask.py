# -*- coding: utf-8 -*-

from __future__ import annotations

from commands.base import BaseCommand
from commands.util import need
from core.types import CommandCall, DispatchResult, ExecutionContext
from core.memory import Memory


class AskCommand(BaseCommand):
    def __init__(self) -> None:
        super().__init__(
            name="ASK",
            prompt_help=(
                """ASK: Ask the user a question and wait for an answer.

Fields:
  QUESTION:
    Text to show the user.

Effect:
  Adds user's answer to BODY in a tagged form.
"""
            ),
        )

    def execute(self, memory: Memory, call: CommandCall, ctx: ExecutionContext) -> DispatchResult:
        if ctx.io is None:
            raise RuntimeError("ASK requires io in ExecutionContext")
        question = need(call.payload, "QUESTION")
        answer = ctx.io.ask(question)
        memory.append_body(f"\n[USER_ANSWER to: {question}]\n{answer}\n")
        memory.add_history(ctx.raw_cmd_block or "<CMD>ASK</CMD>")
        return DispatchResult(memory=memory)
