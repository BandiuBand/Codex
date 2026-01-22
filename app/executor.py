# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .command_parser import parse_cmd_line
from .commands.base import Command
from .io_adapter import IOAdapter
from .memory import Memory


@dataclass
class CommandRegistry:
    commands: Dict[str, Command]

    def get(self, name: str) -> Command:
        k = name.upper().strip()
        if k not in self.commands:
            raise ValueError(f"Невідома команда: {k}")
        return self.commands[k]


@dataclass
class CommandExecutor:
    registry: CommandRegistry
    io: IOAdapter

    def run_validated_cmd_line(self, mem: Memory, cmd_line: str) -> Memory:
        cmd, kv = parse_cmd_line(cmd_line)
        command = self.registry.get(cmd)
        result = command.run(mem, kv, self.io)
        return result.memory
