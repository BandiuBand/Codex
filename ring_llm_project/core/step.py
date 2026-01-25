from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Final, Optional

from core.types import ExecutionContext
from .memory import Memory

RUNTIME_RAW_OUTPUT_KEY: Final[str] = "__runtime_raw_model_output"
RUNTIME_NORMALIZED_OUTPUT_KEY: Final[str] = "__runtime_normalized_output"
RUNTIME_COMMAND_BLOCK_KEY: Final[str] = "__runtime_command_block"
RUNTIME_STOP_SEQUENCE_KEY: Final[str] = "__runtime_stop_sequence"


def mark_stop(memory: Memory) -> None:
    memory.vars[RUNTIME_STOP_SEQUENCE_KEY] = "1"


def clear_stop(memory: Memory) -> None:
    memory.vars.pop(RUNTIME_STOP_SEQUENCE_KEY, None)


def should_stop(memory: Memory) -> bool:
    return memory.vars.get(RUNTIME_STOP_SEQUENCE_KEY) == "1"


class Step(ABC):
    @abstractmethod
    def execute(self, memory: Memory, ctx: Optional[ExecutionContext] = None) -> Memory:
        raise NotImplementedError
