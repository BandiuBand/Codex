from __future__ import annotations

from ring_llm_project.app import AgentApp


def main() -> None:
    app = AgentApp()
    user_text = "Спрроектуй ДС-ДС перетворювач..."
    out = app.run_once(user_text)
    if out:
        print(out)


if __name__ == "__main__":
    main()
