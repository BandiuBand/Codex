# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from core.memory import Memory


@dataclass
class CommandContext:
    # for loop protection etc.
    executed_recent_cmds: list[str]
    repeat_ask_window: int
    repeat_ask_limit: int


@dataclass
class CommandResult:
    ok: bool
    user_message: Optional[str] = None     # message to show to user (if any)
    wait_user: bool = False               # whether we must wait for user input next
    folded_created: bool = False
    stop: bool = False                    # end loop
    error: Optional[str] = None           # internal error reason


class Command:
    def execute(self, args: Dict[str, str], memory: Memory, ctx: CommandContext) -> CommandResult:
        raise NotImplementedError
