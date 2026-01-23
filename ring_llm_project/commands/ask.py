# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict

from commands.base import BaseCommand
from core.dispatcher import DispatchResult
from core.memory import Memory
from utils.text import normalize_newlines


class AskCommand(BaseCommand):
    name = "ASK"

    def execute(self, memory: Memory, args: Dict[str, str]) -> DispatchResult:
        text = normalize_newlines(args.get("text", "")).strip()
        wait = args.get("wait", "0").strip()

        if not text:
            text = "(порожнє питання від моделі)"

        # Log + show to user
        memory.add_history(f"ASSISTANT_ASK: {text}")
        return DispatchResult(
            user_message=text,
            stop_for_user_input=True,
            debug=f"ask(wait={wait})",
        )
