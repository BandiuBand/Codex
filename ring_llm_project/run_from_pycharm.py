# -*- coding: utf-8 -*-

"""PyCharm entrypoint.

Run this file in PyCharm. It will:
- create AgentApp
- run an interactive loop (no CLI args)

Configure LLM endpoints below.
"""

from __future__ import annotations

from app import AgentApp
from core.io import ConsoleIO
from core.llm_client import LLMConfig


# --- CONFIG ---
LMSTUDIO_BASE = "http://127.0.0.1:1234/v1"
SMALL_MODEL = "openai/gpt-oss-20b"  # change
BIG_MODEL = "openai/gpt-oss-20b"    # change


def main() -> None:
    llm_configs = {
        "small": LLMConfig(base_url=LMSTUDIO_BASE, model=SMALL_MODEL, temperature=0.3),
        "big": LLMConfig(base_url=LMSTUDIO_BASE, model=BIG_MODEL, temperature=0.2),
    }
    io = ConsoleIO()
    app = AgentApp(llm_configs=llm_configs, io=io)

    print("=== Ring LLM (PyCharm) ===")
    print("Type your message. '/exit' to stop.")

    while True:
        user_text = input(io.prefix_in)
        if user_text.strip().lower() in {"/exit", "exit", "quit"}:
            break

        out_text = app.run_once(user_text)
        # printing full memory each time can be noisy; keep it but you can disable.
        print(io.prefix_out + "\n" + out_text)


if __name__ == "__main__":
    main()
