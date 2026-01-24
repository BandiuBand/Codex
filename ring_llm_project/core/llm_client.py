from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import time
import requests


@dataclass(frozen=True)
class LLMConfig:
    base_url: str  # e.g. "http://127.0.0.1:1234"
    model: str  # e.g. "openai/gpt-oss-20b"
    api_key: Optional[str] = None
    timeout_s: float = 120.0
    temperature: float = 0.2
    max_tokens: int = -1
    stream: bool = False


class LLMClient:
    """
    OpenAI-compatible client (LM Studio / Cherry-compatible endpoints).
    This class does NOT build prompts. It only sends messages and returns raw text.
    """

    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg

    def chat(self, messages: List[Dict[str, str]]) -> str:
        url = self.cfg.base_url.rstrip("/") + "/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.cfg.api_key:
            headers["Authorization"] = f"Bearer {self.cfg.api_key}"

        payload: Dict[str, Any] = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": self.cfg.temperature,
            "max_tokens": self.cfg.max_tokens,
            "stream": self.cfg.stream,
        }

        t0 = time.time()
        r = requests.post(url, headers=headers, json=payload, timeout=self.cfg.timeout_s)
        r.raise_for_status()
        data = r.json()

        # OpenAI format: choices[0].message.content
        try:
            return data["choices"][0]["message"]["content"]
        finally:
            _ = time.time() - t0
