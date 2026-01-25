# -*- coding: utf-8 -*-
from __future__ import annotations

from commands.base import BaseCommand
from core.types import CommandCall, DispatchResult, ExecutionContext
from core.memory import Memory
from utils.text import normalize_newlines


class SetGoalCommand(BaseCommand):
    @property
    def command_name(self) -> str:
        return "SET_GOAL"

    def execute(self, memory: Memory, call: CommandCall, ctx: ExecutionContext) -> DispatchResult:
        text = normalize_newlines(call.args.get("text", "")).strip()
        if not text:
            return DispatchResult(
                memory=memory,
                user_message="SET_GOAL: порожній text",
                stop_for_user_input=False,
                debug="set_goal_empty",
            )
        memory.set_goal(text)
        add_history = getattr(memory, "add_history", None)
        if callable(add_history):
            add_history("ASSISTANT: (goal updated)")
        else:
            memory.add_event("assistant", "(goal updated)", kind="note")
        return DispatchResult(
            memory=memory,
            user_message=None,
            stop_for_user_input=False,
            debug="set_goal_ok",
        )
