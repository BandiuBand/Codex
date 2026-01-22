# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from config import AppConfig, CommandSpec
from core.memory import Memory
from llm.base import LLMMessage


@dataclass
class PromptBuilder:
    cfg: AppConfig

    def build_messages(self, memory: Memory, user_text: str) -> List[LLMMessage]:
        """
        IMPORTANT: system prompt is English only.
        user_text can be any language (your conversation).
        """
        system_prompt = self._build_system_prompt()
        mem_block = memory.to_text(include_end_marker=True)

        user_prompt = (
            f"{mem_block}\n"
            f"USER_MESSAGE:\n{user_text.strip()}\n"
            f"\n"
            f"Return exactly one command line.\n"
        )

        return [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ]

    def _build_system_prompt(self) -> str:
        # Describe the protocol and allowed commands.
        cmd_lines = []
        for name in sorted(self.cfg.commands.keys()):
            spec: CommandSpec = self.cfg.commands[name]
            args = ", ".join(spec.args) if spec.args else "(no args)"
            cmd_lines.append(f"- {spec.name}: {spec.description} Args: {args}")

        commands_text = "\n".join(cmd_lines)

        return (
            "You are an execution planner for a command-driven assistant.\n"
            "You MUST follow the protocol.\n\n"
            "PROTOCOL:\n"
            "1) Output MUST be a single command line starting with 'CMD '.\n"
            "2) Do NOT output explanations, thoughts, analysis, or extra text.\n"
            "3) If you need to ask the user, use: CMD ASK wait=0 text=\"...\"\n"
            "4) If you cannot proceed, use: CMD ERROR code=\"...\" message=\"...\"\n"
            "5) Commands are case-sensitive only for their name; use UPPERCASE names.\n\n"
            "ALLOWED COMMANDS:\n"
            f"{commands_text}\n\n"
            "MEMORY FORMAT:\n"
            "You will receive a memory snapshot between ===MEMORY=== and ===END_MEMORY===.\n"
            "Use it to decide the next command.\n"
        )
