# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

import requests


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


class OllamaClient:
    """
    Minimal Ollama /api/chat client.
    """
    def __init__(self, base_url: str, model: str, timeout_s: int = 120):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s

    def chat(self, messages: List[ChatMessage]) -> str:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        r = requests.post(url, json=payload, timeout=self.timeout_s)
        r.raise_for_status()
        data = r.json()
        # Expected: {"message":{"role":"assistant","content":"..."}}
        return (data.get("message") or {}).get("content", "")
