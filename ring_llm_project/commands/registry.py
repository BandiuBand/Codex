# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, Optional

from commands.base import BaseCommand


class CommandRegistry:
    def __init__(self):
        self._cmds: Dict[str, BaseCommand] = {}

    def register(self, cmd: BaseCommand) -> None:
        self._cmds[cmd.name.upper()] = cmd

    def get(self, name: str) -> Optional[BaseCommand]:
        return self._cmds.get((name or "").upper())

    def names(self):
        return sorted(self._cmds.keys())
