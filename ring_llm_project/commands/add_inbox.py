# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict

from commands.base import BaseCommand
from core.types import DispatchResult
from core.memory import Memory
from utils.text import normalize_newlines


class AddInboxCommand(BaseCommand):
    name = "ADD_INBOX"

    def execute(self, memory: Memory, args: Dict[str, str]) -> DispatchResult:
        text = normalize_newlines(args.get("text", "")).strip()
        if not text:
            return DispatchResult(user_message=None, stop_for_user_input=False, debug="add_inbox_empty")
        memory.add_inbox(text)
        memory.add_history("ASSISTANT: (inbox updated)")
        return DispatchResult(user_message=None, stop_for_user_input=False, debug="add_inbox_ok")
