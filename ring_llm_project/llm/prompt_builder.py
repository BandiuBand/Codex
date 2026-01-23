# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from config import CommandSpec, AppConfig
from core.memory import Memory


class PromptBuilder:
    """
    IMPORTANT: prompt to model is English only.
    """
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg

    def system_prompt(self, memory: Memory) -> str:
        cmds = self._commands_section(self.cfg.command_specs)

        # English-only system prompt:
        return f"""You are a command-driven assistant.

You MUST output exactly one of the following blocks:

1) A COMMAND block:
{self.cfg.cmd_start}
CMD <NAME> key=value key=value ...
{self.cfg.cmd_end}

2) A MESSAGE block (user-facing text):
{self.cfg.msg_start}
... free text ...
{self.cfg.msg_end}

Rules:
- If you output a COMMAND block, it must contain exactly ONE command line starting with "CMD ".
- If a value contains spaces/newlines/special symbols, use double quotes, e.g. text="hello world".
- If you use quotes inside a quoted value, escape them as \\"
- Do NOT output any thoughts, reasoning, or analysis. If you still produce them, they will be discarded.
- Prefer ASK when you need missing info from the user.
- Otherwise output a MESSAGE block.

Available commands:
{cmds}

Current memory snapshot:
{memory.to_text(include_end_marker=True)}
"""

    def _commands_section(self, specs: List[CommandSpec]) -> str:
        lines = []
        for s in specs:
            args = (" " + " ".join(s.args)) if s.args else ""
            lines.append(f"- {s.name}{args}: {s.help}")
        return "\n".join(lines)
