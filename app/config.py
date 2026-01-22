# -*- coding: utf-8 -*-

from dataclasses import dataclass
from typing import List, Literal


Provider = Literal["openai", "ollama"]
SyntaxMode = Literal["strict_line", "extract_first_cmd", "extract_last_cmd"]


@dataclass
class AppConfig:
    # Провайдер
    provider: Provider = "ollama"

    # OpenAI
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4.1-mini"
    openai_api_key_env: str = "OPENAI_API_KEY"

    # Ollama
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:8b"

    # Генерація
    temperature: float = 0.2
    max_tokens: int = 200

    # "Пам'ять" (грубо: ліміт по символах)
    max_context_chars: int = 20000
    memory_fold_threshold_percent: int = 30

    # Валідатор синтаксису
    syntax_mode: SyntaxMode = "strict_line"

    # Файл стану
    state_file: str = "state.json"

    # Список дозволених команд (для промпта та registry)
    allowed_commands: List[str] = None

    def __post_init__(self) -> None:
        if self.allowed_commands is None:
            self.allowed_commands = [
                "FOLD_REPLY",
                "ASK",
                "SET_CURRENT",
                "APPEND_PLAN",
                "REWRITE_PLAN",
                "FOLD_SECTION",
                "DELETE_SECTION",
                "UNFOLD",
            ]
