# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import urllib.request
from typing import List

from llm.base import LLMClient, LLMMessage
from config import LLMConfig


class OllamaClient(LLMClient):
    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg

    def chat(self, messages: List[LLMMessage], **kwargs) -> str:
        url = self.cfg.base_url.rstrip("/") + "/api/chat"

        payload = {
            "model": self.cfg.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {
                "temperature": self.cfg.temperature,
                "top_p": self.cfg.top_p,
                "num_predict": self.cfg.num_predict,
            },
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )

        with urllib.request.urlopen(req, timeout=self.cfg.timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")

        obj = json.loads(raw)
        # Ollama returns: {"message":{"role":"assistant","content":"..."} ...}
        return (obj.get("message") or {}).get("content") or ""
