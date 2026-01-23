# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class CommandSpec:
    name: str
    help: str
    args: List[str] = field(default_factory=list)


@dataclass
class MemoryConfig:
    max_chars: int = 14000
    auto_fold_keep_last_events: int = 40


@dataclass
class ValidatorConfig:
    mode: str = "embedded"  # "strict" | "embedded"
    require_blocks: bool = False  # if True, accept commands ONLY inside §§CMD_START§§ blocks


@dataclass
class LLMConfig:
    provider: str = "ollama"  # currently only ollama implemented here
    base_url: str = "http://127.0.0.1:11434"
    model: str = "qwen3:8b"
    timeout_s: int = 120


@dataclass
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    validator: ValidatorConfig = field(default_factory=ValidatorConfig)

    # Commands available to model (for prompt + registry validation)
    command_specs: List[CommandSpec] = field(default_factory=lambda: [
        CommandSpec(
            name="ASK",
            help="Ask the user a single question. Stops and waits for user input.",
            args=["wait", "text"],
        ),
        CommandSpec(
            name="SET_GOAL",
            help="Set or replace the current GOAL section.",
            args=["text"],
        ),
        CommandSpec(
            name="SET_VAR",
            help="Set a variable in VARS section.",
            args=["key", "value"],
        ),
        CommandSpec(
            name="ADD_INBOX",
            help="Add an item into INBOX list.",
            args=["text"],
        ),
        CommandSpec(
            name="FOLD_NOW",
            help="Force folding older HISTORY into one FOLDED entry.",
            args=["reason"],
        ),
        CommandSpec(
            name="NOOP",
            help="Do nothing. Useful when model wants to acknowledge without command.",
            args=[],
        ),
    ])

    # UI tags used for robust extraction (rare tokens, ASCII-safe)
    cmd_start: str = "§§CMD_START§§"
    cmd_end: str = "§§CMD_END§§"
    msg_start: str = "§§MSG_START§§"
    msg_end: str = "§§MSG_END§§"
