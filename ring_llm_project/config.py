# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class ValidationMode(str, Enum):
    STRICT_CMD_ONLY = "STRICT_CMD_ONLY"     # output must be ONLY a command line
    EXTRACT_FROM_TEXT = "EXTRACT_FROM_TEXT" # extract last CMD line from any text


@dataclass
class LLMConfig:
    provider: str = "ollama"         # "ollama"
    model: str = "qwen3:8b"
    base_url: str = "http://127.0.0.1:11434"
    temperature: float = 0.2
    top_p: float = 0.9
    num_predict: int = 256
    timeout_s: int = 120


@dataclass
class MemoryConfig:
    max_chars: int = 14000          # used only for memory_fill% + optional auto-fold
    history_max_events: int = 200   # hard cap for history list length
    auto_fold: bool = True
    auto_fold_keep_last_events: int = 30


@dataclass
class CommandSpec:
    name: str
    description: str
    args: List[str] = field(default_factory=list)


@dataclass
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)

    # validator behavior
    validation_mode: ValidationMode = ValidationMode.EXTRACT_FROM_TEXT

    # command registry for validator + prompt
    commands: Dict[str, CommandSpec] = field(default_factory=lambda: {
        "ASK": CommandSpec(
            name="ASK",
            description="Ask the user for missing information. The program will show the question to the user and wait for reply.",
            args=["text", "wait"],
        ),
        "NOTE": CommandSpec(
            name="NOTE",
            description="Write a note into memory (debug/inbox).",
            args=["text", "level"],
        ),
        "SETVAR": CommandSpec(
            name="SETVAR",
            description="Set/update a variable in [VARS].",
            args=["key", "value"],
        ),
        "SETGOAL": CommandSpec(
            name="SETGOAL",
            description="Set/update [GOAL].",
            args=["text"],
        ),
        "PLAN": CommandSpec(
            name="PLAN",
            description="Replace the plan with numbered steps.",
            args=["steps", "current"],
        ),
        "FOLD": CommandSpec(
            name="FOLD",
            description="Create a fold (summary) from part of history.",
            args=["reason", "keep_last"],
        ),
        "DONE": CommandSpec(
            name="DONE",
            description="Finish current cycle / mark completion.",
            args=["text"],
        ),
        "ERROR": CommandSpec(
            name="ERROR",
            description="Signal that the model cannot proceed or protocol failed.",
            args=["code", "message"],
        ),
    })

    # anti-loop protection for repeated ASK
    repeat_ask_window: int = 12
    repeat_ask_limit: int = 2
