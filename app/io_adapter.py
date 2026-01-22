# -*- coding: utf-8 -*-

from __future__ import annotations


class IOAdapter:
    """Інтерфейс вводу/виводу (щоб потім замінити консоль на Telegram/GUI)."""

    def ask_user(self, text: str) -> str:
        raise NotImplementedError


class ConsoleIO(IOAdapter):
    def ask_user(self, text: str) -> str:
        print("\nПовідомлення користувачу:")
        print("----------------------------------------")
        print(text)
        print("----------------------------------------")
        try:
            return input("Відповідь користувача (введи текст і Enter): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return ""
