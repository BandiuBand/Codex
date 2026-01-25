from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol

from core.types import CommandCall, DispatchResult, ExecutionContext
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


class BaseCommand(ABC):
    """
    Atomic command interface.
    Prompt explanation belongs to the command, but 'motivation' belongs to Steps/Chains.
    """
    @property
    @abstractmethod
    def command_name(self) -> str:
        """Exact command name, e.g. 'LOOP DONE'."""
        raise NotImplementedError

    @property
    def prompt_help(self) -> str:
        """
        English-only snippet (you can inject it into Step prompts).
        Must describe ONLY syntax + functionality, no motivation.
        """
        return ""

    @abstractmethod
    def execute(self, memory: Any, call: CommandCall, ctx: ExecutionContext) -> DispatchResult:
        raise NotImplementedError
