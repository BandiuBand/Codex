from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict

import requests


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


@dataclass
class OllamaLLMClient(LLMClient):
    """
    LLM client that calls a local Ollama instance via HTTP API.

    By default expects:
      - base_url: http://localhost:11434
      - model: name of the model loaded into Ollama (e.g. "qwen3:32b")
    """

    base_url: str = "http://localhost:11434"
    model: str = "qwen3:32b"
    timeout: float = 60.0

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """
        Call Ollama /api/generate endpoint and return the 'response' field.

        kwargs may contain:
          - temperature
          - num_ctx
          - top_p
          - інші опції, які Ollama підтримує.
        """
        url = self.base_url.rstrip("/") + "/api/generate"

        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }

        if kwargs:
            payload.update(kwargs)

        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
        except Exception as exc:  # pragma: no cover - network errors are runtime concerns
            raise RuntimeError(f"Ollama request failed: {exc}") from exc

        if resp.status_code != 200:
            raise RuntimeError(f"Ollama returned {resp.status_code}: {resp.text}")

        data = resp.json()
        text = data.get("response")
        if text is None:
            raise RuntimeError(f"Ollama response missing 'response' field: {data}")

        return text
