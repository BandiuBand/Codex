from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class CommandCall:
    """
    Parsed command call from <CMD>...</CMD>.
    Example payload: "LOOP DONE"
    """
    raw: str                 # full inner text, trimmed
    name: str                # normalized command name (e.g. "LOOP DONE")
    args: Dict[str, Any]     # optional parsed args (can be empty)


@dataclass
class DispatchResult:
    """
    Result of executing one command.
    IMPORTANT:
      - loop_done=True must NOT be persisted into memory history.
      - visible_event=False means 'do not log into memory history'.

    Legacy fields are kept for compatibility with older dispatch flows.
    """
    memory: Any = None
    loop_done: bool = False
    visible_event: bool = True
    user_output: Optional[str] = None
    debug_note: Optional[str] = None
    user_message: Optional[str] = None
    stop_for_user_input: bool = False
    debug: str = ""


@dataclass
class ExecutionContext:
    """
    Execution context passed through steps/dispatcher.
    You can extend it later (timestamps, llm_key, debug flags, etc.)
    """
    debug_calls: bool = False
    debug_raw_llm: bool = False
    debug_commands: bool = False
    debug_memory: bool = False
