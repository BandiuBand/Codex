# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass


class IOAdapter:
    def say(self, text: str) -> None:
        raise NotImplementedError

    def ask(self, prompt: str) -> str:
        raise NotImplementedError


@dataclass
class ConsoleIO(IOAdapter):
    prefix_out: str = "ASSISTANT> "
    prefix_in: str = "YOU> "

    def say(self, text: str) -> None:
        print(f"{self.prefix_out}{text}")

    def ask(self, prompt: str) -> str:
        print(f"{self.prefix_out}{prompt}")
        return input(self.prefix_in)
