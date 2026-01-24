from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Protocol
from ring_llm_project.core.memory import Memory


@dataclass(frozen=True)
class CommandContext:
    # hook for UI or external integration (Cherry Studio, etc.)
    io: Optional["IOAdapter"]
    llms: Dict[str, object]  # actual type is LLMClient, but keep generic here to avoid cycles


class IOAdapter(Protocol):
    def show(self, text: str) -> None: ...
    def ask(self, text: str) -> str: ...


class Command(Protocol):
    name: str

    def prompt_fragment(self) -> str:
        """English text fragment describing how to use this command."""
        ...

    def run(self, mem: Memory, args: Dict[str, str], ctx: CommandContext) -> Memory:
        ...
