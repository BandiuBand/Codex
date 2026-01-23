# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict

from commands.base import BaseCommand
from core.types import DispatchResult
from core.memory import Memory


class NoopCommand(BaseCommand):
    name = "NOOP"

    def execute(self, memory: Memory, args: Dict[str, str]) -> DispatchResult:
        memory.add_history("ASSISTANT: (noop)")
        return DispatchResult(user_message=None, stop_for_user_input=False, debug="noop")
