from __future__ import annotations

from ring_llm_project.commands.base import IOAdapter
from ring_llm_project.main import create_process, run_once


class ConsoleIO(IOAdapter):
    def show(self, text: str) -> None:
        print("\nASSISTANT>\n" + text + "\n")

    def ask(self, text: str) -> str:
        print("\nASSISTANT (ASK)>\n" + text + "\n")
        return input("YOU> ")


def main() -> None:
    process = create_process(io=ConsoleIO())

    while True:
        user = input("YOU> ").strip()
        if user.lower() in {"/exit", "exit", "quit"}:
            break
        run_once(process, user)


if __name__ == "__main__":
    main()
