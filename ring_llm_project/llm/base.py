# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class LLMMessage:
    role: str   # "system" | "user" | "assistant"
    content: str


class LLMClient:
    def chat(self, messages: List[LLMMessage], **kwargs) -> str:
        raise NotImplementedError
