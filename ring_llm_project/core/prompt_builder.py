from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List
from ring_llm_project.core.memory import Memory
from ring_llm_project.commands.registry import CommandRegistry


@dataclass(frozen=True)
class PromptConfig:
    system_role: str = "system"


class PromptBuilder:
    def __init__(self, cfg: PromptConfig, registry: CommandRegistry, validator_help: str):
        self.cfg = cfg
        self.registry = registry
        self.validator_help = validator_help

    def build_messages(self, mem: Memory) -> List[Dict[str, str]]:
        # English-only system prompt
        cmd_help = "\n".join(cmd.prompt_fragment() for cmd in self.registry.all().values())

        system = (
            "You are a command-driven assistant.\n"
            "You may either:\n"
            "- Output normal assistant text (no command), OR\n"
            "- Output exactly one command block with a name and payload.\n\n"
            "COMMAND FORMAT:\n"
            f"{self.validator_help}\n\n"
            "AVAILABLE COMMANDS:\n"
            f"{cmd_help}\n\n"
            "MEMORY SNAPSHOT (read-only):\n"
            f"{mem.to_text()}\n"
        )

        # Last user message is already in memory history, but we pass explicit final user turn too:
        last_user = ""
        for ev in reversed(mem.history):
            if ev.role == "user":
                last_user = ev.text
                break

        return [
            {"role": self.cfg.system_role, "content": system},
            {"role": "user", "content": last_user},
        ]
