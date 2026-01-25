# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests


@dataclass(frozen=True)
class LLMConfig:
    base_url: str  # e.g. "http://127.0.0.1:1234/v1"
    model: str
    api_key: str = ""  # LM Studio usually ignores; keep for compatibility
    temperature: float = 0.2
    max_tokens: int = 1024
    timeout_s: float = 120.0


class LLMClient:
    """OpenAI-compatible chat completions client (LM Studio / Cherry Studio backend)."""

    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg

    def chat(self, messages: List[Dict[str, str]]) -> str:
        url = self.cfg.base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.cfg.api_key:
            headers["Authorization"] = f"Bearer {self.cfg.api_key}"

        payload: Dict[str, Any] = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": self.cfg.temperature,
            "max_tokens": self.cfg.max_tokens,
            "stream": False,
        }

        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=self.cfg.timeout_s)
        r.raise_for_status()
        data = r.json()
        # OpenAI format
        return data["choices"][0]["message"]["content"]
