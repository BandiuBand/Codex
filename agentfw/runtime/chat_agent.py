from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional

from agentfw.core.envelope import AgentEnvelope
from agentfw.runtime.engine import ExecutionEngine, ExecutionState


@dataclass
class ChatResponse:
    conversation_id: str
    status: str
    message: AgentEnvelope
    run_id: Optional[str]
    state: ExecutionState


class ChatConversation:
    def __init__(self, conversation_id: Optional[str] = None) -> None:
        self.conversation_id = conversation_id or str(uuid.uuid4())
        self.history: List[AgentEnvelope] = []
        self.last_state: Optional[ExecutionState] = None

    def record(self, envelope: AgentEnvelope) -> None:
        self.history.append(envelope)


class ChatAgentGateway:
    """Mінімальний шлюз між UI та ExecutionEngine.

    Він тримає історію переписки та гарантує, що всі запити
    проходять через єдиний вхід ChatAgent.
    """

    def __init__(
        self,
        engine: ExecutionEngine,
        orchestrator: str = "adaptive_task_agent",
        *,
        default_max_reviews: int = 1,
    ) -> None:
        self.engine = engine
        self.orchestrator = orchestrator
        self.default_max_reviews = default_max_reviews
        self._conversations: Dict[str, ChatConversation] = {}

    def send_user_message(
        self,
        content: str,
        *,
        conversation_id: Optional[str] = None,
        attachments: Optional[List[Dict[str, object]]] = None,
        expected_output: Optional[str] = None,
    ) -> ChatResponse:
        conversation = self._get_or_create(conversation_id)
        clean_content = (content or "").strip()
        has_user_message = bool(clean_content)

        if not has_user_message and conversation.last_state and conversation.last_state.status == "blocked":
            last_chat_reply = next((msg for msg in reversed(conversation.history) if msg.role == "chat"), None)
            if last_chat_reply:
                return ChatResponse(
                    conversation_id=conversation.conversation_id,
                    status=conversation.last_state.status,
                    message=last_chat_reply,
                    run_id=conversation.last_state.run_id,
                    state=conversation.last_state,
                )

        if has_user_message:
            user_envelope = AgentEnvelope(
                conversation_id=conversation.conversation_id,
                message_id=str(uuid.uuid4()),
                role="user",
                timestamp=time.time(),
                content=clean_content,
                attachments=list(attachments or []),
                expected_output=expected_output,
            )
            conversation.record(user_envelope)

        try:
            payload: Dict[str, object] = {"max_reviews": self.default_max_reviews}
            if has_user_message:
                payload.update({"завдання": clean_content, "user_message": clean_content})
            if expected_output is not None:
                payload["expected_output"] = expected_output
            if attachments:
                payload["attachments"] = attachments
            state = self.engine.run_to_completion(
                self.orchestrator,
                input_json=payload,
                raise_on_error=False,
            )
        except Exception as exc:  # noqa: BLE001
            state = ExecutionState(
                agent_name=self.orchestrator,
                run_id=str(uuid.uuid4()),
                status="error",
                ok=False,
                vars={},
                trace=[],
                error=str(exc),
            )

        reply_content = self._extract_reply_content(state)
        reply_envelope = AgentEnvelope(
            conversation_id=conversation.conversation_id,
            message_id=str(uuid.uuid4()),
            role="chat",
            timestamp=time.time(),
            content=reply_content,
            expected_output=self._infer_expected_output(state),
            status=state.status,
            missing_inputs=state.missing_inputs,
            questions_to_user=state.questions_to_user,
            why_blocked=state.why_blocked,
        )
        conversation.record(reply_envelope)
        conversation.last_state = state

        return ChatResponse(
            conversation_id=conversation.conversation_id,
            status=state.status,
            message=reply_envelope,
            run_id=state.run_id,
            state=state,
        )

    def history(self, conversation_id: str) -> List[AgentEnvelope]:
        conversation = self._conversations.get(conversation_id)
        return list(conversation.history) if conversation else []

    def _get_or_create(self, conversation_id: Optional[str]) -> ChatConversation:
        if conversation_id and conversation_id in self._conversations:
            return self._conversations[conversation_id]
        conversation = ChatConversation(conversation_id)
        self._conversations[conversation.conversation_id] = conversation
        return conversation

    @staticmethod
    def _extract_reply_content(state: ExecutionState) -> str:
        if state.status == "error":
            return state.error or "Сталася помилка"
        if state.status == "blocked":
            return state.why_blocked or "Потрібні уточнення для продовження"
        for key in ("final_message_to_user", "final_message", "результат", "result", "output_text"):
            value = state.vars.get(key)
            if value:
                return str(value)
        return json.dumps(state.vars, ensure_ascii=False)

    @staticmethod
    def _infer_expected_output(state: ExecutionState) -> Optional[str]:
        if state.status == "blocked":
            return "question"
        if "file" in {k.lower() for k in state.vars.keys()}:
            return "file_written"
        return "final"


__all__ = ["ChatAgentGateway", "ChatConversation", "ChatResponse"]
