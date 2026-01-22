# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import List

import requests

from .config import AppConfig


_THINK_BLOCK_RE = re.compile(r"<think>.*?(</think>|$)", re.DOTALL | re.IGNORECASE)


def normalize_text(s: str) -> str:
    text = (s or "").replace("\r\n", "\n").replace("\r", "\n")
    text = _THINK_BLOCK_RE.sub("", text)
    text = " ".join(x.strip() for x in text.split("\n") if x.strip())
    return text.strip()


@dataclass
class LLMClient:
    cfg: AppConfig

    def build_system_prompt(self) -> str:
        # English only (as requested)
        allowed = ", ".join(self.cfg.allowed_commands)

        return f"""You are a single-step executor inside an orchestrated system.

Hard constraints:
- You MUST output EXACTLY ONE command per response.
- Output MUST be a single line starting with "CMD ".
- You MUST NOT output any explanations, greetings, or extra text.
- You MUST NOT output the backslash character.
- You MUST NOT output JSON, markdown, code blocks, or quotes in the command.
- If you violate format, the orchestrator will re-ask the same prompt.

You have "Memory" provided in the message. Memory is the ONLY state.
The orchestrator executes your command, updates Memory, then calls you again.

State model:
- HISTORY is the state machine log of what happened.
- INBOX contains pending user replies that are NOT processed yet.
- VARS contains already-processed facts (structured variables).
- PLAN contains the step-by-step plan and the current step pointer.
- PENDING describes which variable you are currently waiting for (if any).

Priority rule (strict):
1) If INBOX has any USER_REPLY items -> you MUST process ONE of them now using CMD FOLD_REPLY.
2) Else, if PENDING is set (pending_var exists) -> you MUST NOT ask anything. You should either update CURRENT to "waiting for <var>" OR fold/compress noise if memory is high.
3) Else, if memory_fill > 30% -> you MUST fold/compress something low-priority.
4) Else -> you either update PLAN/CURRENT step OR ask a new question for exactly ONE missing variable.

Never repeat questions:
- Before asking anything, check VARS and PENDING.
- If a variable already exists in VARS, you MUST NOT ask for it again.
- If PENDING is set, you MUST NOT ask a new question.

Critical ASK rule:
- Every ASK must declare which variable you are requesting: var=<name>.
- Every ASK MUST use wait=1 (blocking). Using wait=0 is forbidden.
- After ASK var=<x>, the next time you see a USER_REPLY you MUST fold it into the SAME var=<x>.

Processing a user reply (mandatory protocol):
- A reply appears as USER_REPLY id=<n> text=<...> inside INBOX.
- Replies are NOT usable until you convert them into a VAR with CMD FOLD_REPLY.
- Converting means: create ONE variable from that reply.

Naming rules for variables:
- Use short, machine-friendly names: ripple_vout, ripple_iin, vin_range, vout, iout, phases, freq_eff, controller, topology, etc.
- Provide a short normalized value (no long sentences).

Command format (one line):
CMD <COMMAND_NAME> key=value key=value ... text=<free text to end of line>
- Do NOT use quotes.

Allowed commands:
{allowed}

REMEMBER:
- If INBOX has any USER_REPLY -> ONLY CMD FOLD_REPLY is valid.
- ASK must be wait=1 and must include var=.
- Exactly one CMD line. Nothing else.
"""

    def call(self, memory_snapshot: str) -> str:
        system_prompt = self.build_system_prompt()

        if self.cfg.provider == "openai":
            api_key = os.getenv(self.cfg.openai_api_key_env, "").strip()
            if not api_key:
                raise RuntimeError(f"Немає ключа OpenAI. Задай {self.cfg.openai_api_key_env} в оточенні.")

            url = f"{self.cfg.openai_base_url}/chat/completions"
            payload = {
                "model": self.cfg.openai_model,
                "temperature": self.cfg.temperature,
                "max_tokens": self.cfg.max_tokens,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": memory_snapshot},
                ],
            }
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=120)
            if r.status_code != 200:
                raise RuntimeError(f"OpenAI HTTP {r.status_code}: {r.text}")
            data = r.json()
            return normalize_text(data["choices"][0]["message"]["content"])

        if self.cfg.provider == "ollama":
            url = f"{self.cfg.ollama_url}/api/chat"
            payload = {
                "model": self.cfg.ollama_model,
                "stream": False,
                "options": {
                    "temperature": self.cfg.temperature,
                    "num_predict": self.cfg.max_tokens,
                },
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": memory_snapshot},
                ],
            }
            r = requests.post(url, data=json.dumps(payload), headers={"Content-Type": "application/json"}, timeout=120)
            if r.status_code != 200:
                raise RuntimeError(f"Ollama HTTP {r.status_code}: {r.text}")
            data = r.json()
            return normalize_text(data["message"]["content"])

        raise RuntimeError(f"Невідомий provider={self.cfg.provider}")
