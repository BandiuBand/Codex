from __future__ import annotations
from dataclasses import dataclass
from typing import Dict
from .llm_client import LLMClient


@dataclass(frozen=True)
class LLMRouter:
    llms: Dict[str, LLMClient]

    def get(self, key: str) -> LLMClient:
        if key not in self.llms:
            raise KeyError(f"LLM key not found: {key}. Available: {list(self.llms.keys())}")
        return self.llms[key]
