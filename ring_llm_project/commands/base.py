# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.types import CommandCall, DispatchResult, ExecutionContext
from core.memory import Memory


@dataclass
class BaseCommand:
    name: str
    prompt_help: str

    def execute(self, memory: Memory, call: CommandCall, ctx: ExecutionContext) -> DispatchResult:
        raise NotImplementedError


class CommandError(Exception):
    pass
