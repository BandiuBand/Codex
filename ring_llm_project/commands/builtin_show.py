from __future__ import annotations
from typing import Dict
from .base import CommandContext
from ring_llm_project.core.memory import Memory


class ShowCommand:
    name = "SHOW"

    def prompt_fragment(self) -> str:
        return (
            "Command SHOW: show a message to the user.\n"
            "Usage:\n"
            "<CMD>\n"
            "SHOW\n"
            "message...\n"
            "</CMD>\n"
        )

    def run(self, mem: Memory, args: Dict[str, str], ctx: CommandContext) -> Memory:
        text = args.get("payload", "")
        mem.add_event("assistant", text, kind="msg")
        if ctx.io:
            ctx.io.show(text)
        return mem
