# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from core.types import CommandCall, DispatchResult, ExecutionContext


class CommandRegistry:
    def __init__(self) -> None:
        self._cmds: Dict[str, object] = {}

    def register(self, cmd: object) -> None:
        # command must expose .name and .execute(memory, call, ctx)
        name = getattr(cmd, "name", None)
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Command {cmd!r} has invalid .name")
        self._cmds[name.upper()] = cmd

    def get(self, name: str) -> object:
        key = name.upper().strip()
        if key not in self._cmds:
            raise KeyError(f"Unknown command: {name}")
        return self._cmds[key]

    def prompt_help_all(self) -> str:
        lines = []
        for name in sorted(self._cmds.keys()):
            cmd = self._cmds[name]
            help_text = getattr(cmd, "prompt_help", "").strip()
            if help_text:
                lines.append(help_text)
        return "\n\n".join(lines)


@dataclass
class CommandDispatcher:
    registry: CommandRegistry

    def dispatch(self, memory, call: CommandCall, ctx: ExecutionContext) -> DispatchResult:
        cmd = self.registry.get(call.name)
        execute = getattr(cmd, "execute", None)
        if not callable(execute):
            raise TypeError(f"Command {call.name} has no callable execute()")
        return execute(memory, call, ctx)
