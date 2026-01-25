# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Protocol, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from core.memory import Memory


@dataclass(frozen=True)
class CommandCall:
    """Command parsed from a <CMD> block.

    The block format is:
        <CMD>
        COMMAND_NAME
        KEY1:
        value...
        KEY2:
        value...
        </CMD>

    payload_text is the raw text after the first line (command name).
    payload is a best-effort KEY->VALUE mapping, extracted by the parser.
    """

    name: str
    payload_text: str = ""
    payload: Dict[str, str] = field(default_factory=dict)


@dataclass
class DispatchResult:
    """Result of executing a command or step."""

    memory: 'Memory'
    # Text that should be shown to the user (optional, depending on IO layer)
    user_output: Optional[str] = None
    # If True, a StepLoop should stop.
    break_loop: bool = False


@dataclass
class ExecutionContext:
    """Execution context passed across the engine."""

    # Models pool: key -> LLM client
    llm_pool: Dict[str, object]

    # Active model key for this step/command (optional convenience)
    model_key: str = "big"

    # IO interface (Console, Cherry Studio hook, etc.)
    io: Optional[object] = None

    # Debug flags
    debug_calls: bool = False
    debug_raw_llm: bool = False
    debug_cmd: bool = False
    debug_memory: bool = False


class Step(Protocol):
    def execute(self, memory: 'Memory', ctx: ExecutionContext) -> DispatchResult:
        ...
