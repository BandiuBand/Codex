# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict

from commands.base import BaseCommand
from core.types import DispatchResult
from core.memory import Memory
from utils.text import normalize_newlines


class SetVarCommand(BaseCommand):
    name = "SET_VAR"

    def execute(self, memory: Memory, args: Dict[str, str]) -> DispatchResult:
        key = normalize_newlines(args.get("key", "")).strip()
        value = normalize_newlines(args.get("value", "")).strip()
        if not key:
            return DispatchResult(user_message="SET_VAR: порожній key", stop_for_user_input=False, debug="set_var_empty_key")
        memory.set_var(key, value)
        memory.add_history(f"ASSISTANT: (var set {key})")
        return DispatchResult(user_message=None, stop_for_user_input=False, debug="set_var_ok")
