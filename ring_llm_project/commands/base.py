# -*- coding: utf-8 -*-
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict

from core.memory import Memory
from core.types import DispatchResult


class BaseCommand(ABC):
    name: str = ""

    @abstractmethod
    def execute(self, memory: Memory, args: Dict[str, str]) -> DispatchResult:
        raise NotImplementedError
