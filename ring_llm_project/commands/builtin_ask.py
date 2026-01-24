from __future__ import annotations
import hashlib
import time
from typing import Dict
from .base import CommandContext
from ring_llm_project.core.memory import Memory


def _question_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]


class AskCommand:
    name = "ASK"

    def prompt_fragment(self) -> str:
        return (
            "Command ASK: ask the user a question and store the user's answer in memory.\n"
            "Usage:\n"
            "<CMD>\n"
            "ASK\n"
            "question...\n"
            "</CMD>\n"
        )

    def run(self, mem: Memory, args: Dict[str, str], ctx: CommandContext) -> Memory:
        q = args.get("payload", "")
        fold_id = args.get("fold_id")
        q_id = _question_id(q)
        mem.add_event("assistant", q, kind="ask")

        if not ctx.io:
            # no interactive IO: just record question
            return mem

        answer = ctx.io.ask(q)
        mem.add_event("user", answer, kind="answer")
        answer_event = {
            "ts": str(time.time()),
            "kind": "answer",
            "question_id": q_id,
        }
        if isinstance(fold_id, str) and fold_id.strip():
            answer_event["fold_id"] = fold_id.strip()
        mem.add_event(answer_event)
        return mem
