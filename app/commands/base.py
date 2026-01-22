# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from ..memory import Memory
from ..io_adapter import IOAdapter


@dataclass
class CommandResult:
    memory: Memory
    # Якщо команда хоче зробити "вивід користувачу" (напр. ASK) — тут текст
    user_message: str = ""


class Command:
    name: str = ""

    def run(self, mem: Memory, kv: Dict[str, str], io: IOAdapter) -> CommandResult:
        raise NotImplementedError
