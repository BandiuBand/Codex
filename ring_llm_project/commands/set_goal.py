# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict

from commands.base import BaseCommand
from core.dispatcher import DispatchResult
from core.memory import Memory
from utils.text import normalize_newlines


class SetGoalCommand(BaseCommand):
    name = "SET_GOAL"

    def execute(self, memory: Memory, args: Dict[str, str]) -> DispatchResult:
        text = normalize_newlines(args.get("text", "")).strip()
        if not text:
            return DispatchResult(user_message="SET_GOAL: порожній text", stop_for_user_input=False, debug="set_goal_empty")
        memory.set_goal(text)
        memory.add_history("ASSISTANT: (goal updated)")
        return DispatchResult(user_message=None, stop_for_user_input=False, debug="set_goal_ok")
