from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


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
    def from_file(cls, path: Path) -> "LLMConfig":
        if not path.exists():
            raise FileNotFoundError(
                f"Не знайдено файл конфігурації LLM за шляхом {path}. "
                "Додайте llm_config.yaml поряд з агентами."
            )

        data = yaml.safe_load(path.read_text())
        if not isinstance(data, dict):
            raise ValueError("llm_config.yaml має бути мапою з полями backend/base_url/model")

        backend_raw = data.get("backend") or "ollama"
        backend = str(backend_raw).lower().strip()
        base_url = data.get("base_url")
        model = data.get("model")
        api_key = data.get("api_key")

        return cls(
            backend=backend,
            base_url=str(base_url) if base_url else "http://localhost:11434",
            model=str(model) if model else "qwen3:32b",
            api_key=str(api_key) if api_key else None,
        )
