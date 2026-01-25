# -*- coding: utf-8 -*-
from __future__ import annotations

from commands.base import BaseCommand
from core.types import CommandCall, DispatchResult, ExecutionContext
from core.memory import Memory
from utils.text import normalize_newlines


class SetVarCommand(BaseCommand):
    @property
    def command_name(self) -> str:
        return "SET_VAR"

    def execute(self, memory: Memory, call: CommandCall, ctx: ExecutionContext) -> DispatchResult:
        key = normalize_newlines(call.args.get("key", "")).strip()
        value = normalize_newlines(call.args.get("value", "")).strip()
        if not key:
            return DispatchResult(
                memory=memory,
                user_message="SET_VAR: порожній key",
                stop_for_user_input=False,
                debug="set_var_empty_key",
            )
        memory.set_var(key, value)
        add_history = getattr(memory, "add_history", None)
        if callable(add_history):
            add_history(f"ASSISTANT: (var set {key})")
        else:
            memory.add_event("assistant", f"(var set {key})", kind="note")
        return DispatchResult(
            memory=memory,
            user_message=None,
            stop_for_user_input=False,
            debug="set_var_ok",
        )
