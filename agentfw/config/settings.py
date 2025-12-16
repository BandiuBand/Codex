from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMConfig:
    """
    Runtime configuration for LLM backend selection.
    """

    backend: str = "dummy"  # "dummy" or "ollama"
    base_url: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None

    @classmethod
    def from_env(cls) -> "LLMConfig":
        backend_env = os.getenv("AGENTFW_LLM_BACKEND")
        # Якщо бекенд явно не вказано, але є ознаки налаштування Ollama, обираємо його.
        backend = (
            backend_env.lower()
            if backend_env
            else (
                "ollama"
                if any(
                    key in os.environ
                    for key in ("OLLAMA_MODEL", "OLLAMA_BASE_URL", "OLLAMA_API_KEY")
                )
                else "dummy"
            )
        )

        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        model = os.getenv("OLLAMA_MODEL", "qwen3:32b")
        api_key = os.getenv("OLLAMA_API_KEY")

        # для backend="dummy" base_url/model не критичні, але все одно зчитуємо
        return cls(
            backend=backend,
            base_url=base_url,
            model=model,
            api_key=api_key,
        )
