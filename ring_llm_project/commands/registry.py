from __future__ import annotations
from typing import Dict
from .base import Command


class CommandRegistry:
    def __init__(self):
        self._cmds: Dict[str, Command] = {}

    def register(self, cmd: Command) -> None:
        self._cmds[cmd.name] = cmd

    def get(self, name: str) -> Command:
        if name not in self._cmds:
            raise KeyError(f"Unknown command: {name}")
        return self._cmds[name]

    def all(self) -> Dict[str, Command]:
        return dict(self._cmds)
