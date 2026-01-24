from __future__ import annotations
from typing import Dict
from .base import CommandContext
from ring_llm_project.core.memory import Memory


class AskCommand:
    name = "ASK"

    def prompt_fragment(self) -> str:
        return (
            "Command ASK: ask the user a question and store the user's answer in memory.\n"
            "Usage:\n"
            "@CMD ASK\n"
            "text: |\n"
            "  question...\n"
            "@END\n"
        )

    def run(self, mem: Memory, args: Dict[str, str], ctx: CommandContext) -> Memory:
        q = args.get("text", "")
        mem.add_event("assistant", q, kind="ask")

        if not ctx.io:
            # no interactive IO: just record question
            return mem

        answer = ctx.io.ask(q)
        mem.add_event("user", answer, kind="answer")
        return mem
