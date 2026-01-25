from __future__ import annotations
from typing import Dict, Protocol
from .base import BaseCommand, Command


class _NamedCommand(Protocol):
    command_name: str


RegistryCommand = BaseCommand | Command | _NamedCommand


class CommandRegistry:
    def __init__(self):
        self._cmds: Dict[str, RegistryCommand] = {}

    def register(self, cmd: RegistryCommand) -> None:
        if isinstance(cmd, BaseCommand):
            name = cmd.command_name
        else:
            name = getattr(cmd, "name", None) or getattr(cmd, "command_name", None)
        if not isinstance(name, str) or not name:
            raise ValueError("CommandRegistry.register: command must define a name or command_name")
        self._cmds[name] = cmd

    def get(self, name: str) -> RegistryCommand:
        if name not in self._cmds:
            raise KeyError(f"Unknown command: {name}")
        return self._cmds[name]

    def all(self) -> Dict[str, RegistryCommand]:
        return dict(self._cmds)
