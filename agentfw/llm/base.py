from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


class LLMClient(ABC):
    """Abstract base class for low-level LLM clients."""

    @abstractmethod
    def generate(self, prompt: str, **kwargs: Any) -> str:
        """
        Generate a text response for the given prompt.

        kwargs may contain model-specific options such as temperature, max_tokens, etc.
        """
        raise NotImplementedError


@dataclass
class DummyLLMClient(LLMClient):
    """
    Simple test client that does not call any real model.
    Useful for demos and unit tests.
    """

    prefix: str = "LLM: "

    def generate(self, prompt: str, **kwargs: Any) -> str:
        # На цьому етапі просто повертаємо префікс + промпт
        return f"{self.prefix}{prompt}"
