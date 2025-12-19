from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

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
    LLM client that calls a local or remote Ollama instance via HTTP API.

    Credentials / config:
      - base_url: Ollama endpoint, e.g. http://localhost:11434
      - model: model name loaded into Ollama, e.g. "qwen3:32b"
      - api_key: optional token if Ollama is behind an authenticated proxy
    """

    base_url: str = "http://localhost:11434"
    model: str = "qwen3:32b"
    timeout: float = 600.0
    api_key: Optional[str] = None

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """
        Call Ollama /api/generate endpoint and return the 'response' field.

        kwargs may contain model options such as temperature, num_ctx, etc.
        """
        url = self.base_url.rstrip("/") + "/api/generate"

        request_timeout = kwargs.pop("request_timeout", None)
        if request_timeout is None:
            request_timeout = kwargs.pop("timeout", None)
        try:
            effective_timeout = float(request_timeout) if request_timeout is not None else self.timeout
        except (TypeError, ValueError):  # noqa: BLE001
            effective_timeout = self.timeout

        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }

        if kwargs:
            payload.update(kwargs)

        headers: Dict[str, str] = {}
        if self.api_key:
            # на випадок, якщо надалі буде стояти проксі з авторизацією
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            resp = requests.post(
                url, json=payload, headers=headers, timeout=effective_timeout
            )
        except Exception as exc:  # pragma: no cover - network errors are runtime concerns
            raise RuntimeError(f"Ollama request failed: {exc}") from exc

        if resp.status_code != 200:
            raise RuntimeError(f"Ollama returned {resp.status_code}: {resp.text}")

        data = resp.json()
        text = data.get("response")
        if text is None:
            raise RuntimeError(f"Ollama response missing 'response' field: {data}")

        return text
