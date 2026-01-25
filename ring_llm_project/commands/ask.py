# -*- coding: utf-8 -*-
from __future__ import annotations

from commands.base import BaseCommand
from core.types import CommandCall, DispatchResult, ExecutionContext
from core.memory import Memory
from utils.text import normalize_newlines


class AskCommand(BaseCommand):
    @property
    def command_name(self) -> str:
        return "ASK"

    def execute(self, memory: Memory, call: CommandCall, ctx: ExecutionContext) -> DispatchResult:
        text = normalize_newlines(call.args.get("text", "")).strip()
        wait = call.args.get("wait", "0").strip()

        if not text:
            text = "(порожнє питання від моделі)"

        add_history = getattr(memory, "add_history", None)
        if callable(add_history):
            add_history(f"ASSISTANT_ASK: {text}")
        else:
            memory.add_event("assistant", text, kind="ask")
        return DispatchResult(
            memory=memory,
            user_message=text,
            stop_for_user_input=True,
            debug=f"ask(wait={wait})",
        )
