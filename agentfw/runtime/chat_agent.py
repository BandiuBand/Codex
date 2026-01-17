from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Condition
from typing import Dict, List, Optional


@dataclass
class ChatMessage:
    id: int
    ts: float
    role: str  # "agent" | "user" | "system"
    author: str
    text: str
    meta: Dict[str, object] = field(default_factory=dict)


@dataclass
class ChatState:
    history: List[ChatMessage] = field(default_factory=list)
    pending_input: Optional[Dict[str, object]] = None


class ChatAgentGateway:
    """Простий чат-брокер згідно з CONCEPT.md.

    - один глобальний чат, що живе разом із процесом сервера;
    - історія лиш у RAM;
    - без сесій та автозапусків; агент сам питає та чекає.
    """

    def __init__(self) -> None:
        self.state = ChatState()
        self._next_id = 1
        self._condition = Condition()
        self._pending_answer: Optional[str] = None

    # Public API ---------------------------------------------------------
    def post_agent(self, author: str, text: str, meta: Optional[Dict[str, object]] = None) -> ChatMessage:
        message = self._create_message("agent", author, text, meta=meta)
        return message

    def post_user(self, text: str) -> ChatMessage:
        message = self._create_message("user", "user", text)
        with self._condition:
            if self.state.pending_input:
                self._pending_answer = message.text
                self._condition.notify_all()
        return message

    def ask_user(self, author: str, question_text: str) -> ChatMessage:
        message = self.post_agent(author, question_text)
        self.state.pending_input = {"requested_by": author, "question_msg_id": message.id}
        return message

    def wait_user(self, timeout: Optional[float] = None) -> str:
        with self._condition:
            if not self.state.pending_input:
                raise RuntimeError("Немає активного запитання до користувача")
            if timeout is None:
                while not self._pending_answer:
                    self._condition.wait()
            else:
                deadline = time.monotonic() + timeout
                while not self._pending_answer:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("Відповідь користувача не надійшла вчасно")
                    self._condition.wait(timeout=remaining)
            answer = self._pending_answer
            self._pending_answer = None
            self.state.pending_input = None
            return answer

    def history(self, *, after: Optional[int] = None, limit: int = 100) -> List[ChatMessage]:
        if after is None:
            return self.state.history[-limit:]
        return [msg for msg in self.state.history if msg.id > after][-limit:]

    # Internals ---------------------------------------------------------
    def _create_message(self, role: str, author: str, text: str, *, meta: Optional[Dict[str, object]] = None) -> ChatMessage:
        clean = (text or "").strip()
        if not clean:
            raise ValueError("text обов'язковий")
        message = ChatMessage(id=self._next_id, ts=time.time(), role=role, author=author, text=clean, meta=dict(meta or {}))
        self._next_id += 1
        self.state.history.append(message)
        return message


__all__ = ["ChatAgentGateway", "ChatMessage", "ChatState"]
