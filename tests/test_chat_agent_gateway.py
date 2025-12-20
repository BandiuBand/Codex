from __future__ import annotations

import json
from typing import Any, Dict, List

import pytest

from agentfw.core.envelope import AgentEnvelope
from agentfw.runtime.chat_agent import ChatAgentGateway
from agentfw.runtime.engine import ExecutionState


class DummyEngine:
    def __init__(self, states: List[ExecutionState]) -> None:
        self.states = states
        self.calls: List[Dict[str, Any]] = []

    def run_to_completion(
        self,
        agent_name: str,
        input_json: Dict[str, Any],
        *,
        raise_on_error: bool = True,
    ) -> ExecutionState:
        self.calls.append({"agent": agent_name, "input": input_json})
        if not self.states:
            raise AssertionError("No more states configured")
        return self.states.pop(0)


def _state(status: str, *, vars: Dict[str, Any] | None = None, **extras: Any) -> ExecutionState:  # noqa: A002
    return ExecutionState(
        agent_name="orchestrator",
        run_id="run-1",
        status=status,
        vars=vars or {},
        trace=[],
        ok=status == "ok",
        **extras,
    )


def test_chat_agent_blocks_and_echoes_questions() -> None:
    engine = DummyEngine(
        [
            _state(
                "blocked",
                vars={},
                missing_inputs=["project_root"],
                questions_to_user=["Де проект?"],
                why_blocked="Не вистачає шляху до проекту",
            )
        ]
    )
    gateway = ChatAgentGateway(engine, orchestrator="orchestrator")

    response = gateway.send_user_message("Привіт")

    assert response.status == "blocked"
    assert response.conversation_id
    assert response.message.status == "blocked"
    assert response.message.questions_to_user == ["Де проект?"]
    assert response.message.why_blocked == "Не вистачає шляху до проекту"

    assert len(engine.calls) == 1
    payload = engine.calls[0]["input"]
    assert payload["завдання"] == "Привіт"
    assert payload["user_message"] == "Привіт"


def test_chat_agent_reuses_conversation_history() -> None:
    engine = DummyEngine(
        [
            _state("ok", vars={"final_message_to_user": "done"}),
            _state("ok", vars={"result": "second"}),
        ]
    )
    gateway = ChatAgentGateway(engine, orchestrator="orchestrator")

    first = gateway.send_user_message("Task one")
    second = gateway.send_user_message("Task two", conversation_id=first.conversation_id)

    assert first.conversation_id == second.conversation_id
    history = gateway.history(first.conversation_id)
    assert [msg.role for msg in history] == ["user", "chat", "user", "chat"]
    assert history[-1].content == "second"
    assert history[-3].content == "done"


def test_chat_agent_serializes_state_when_no_text_result() -> None:
    state_vars = {"data": {"nested": True}}
    engine = DummyEngine([_state("ok", vars=state_vars)])
    gateway = ChatAgentGateway(engine)

    response = gateway.send_user_message("Show data")

    assert json.loads(response.message.content) == state_vars


def test_chat_agent_requires_message_content() -> None:
    engine = DummyEngine([_state("ok", vars={})])
    gateway = ChatAgentGateway(engine)

    with pytest.raises(TypeError):  # missing message argument
        gateway.send_user_message()  # type: ignore[arg-type]


def test_chat_agent_preserves_attachment_list() -> None:
    engine = DummyEngine([_state("ok", vars={"result": "ok"})])
    gateway = ChatAgentGateway(engine)

    gateway.send_user_message("hello", attachments=[{"name": "file.txt"}])

    assert engine.calls[0]["input"]["attachments"] == [{"name": "file.txt"}]


def test_chat_agent_supplies_default_max_reviews() -> None:
    engine = DummyEngine([_state("ok", vars={"result": "ok"})])
    gateway = ChatAgentGateway(engine, default_max_reviews=2)

    gateway.send_user_message("do it")

    assert engine.calls[0]["input"]["max_reviews"] == 2


def test_chat_agent_does_not_log_empty_user_message() -> None:
    engine = DummyEngine(
        [
            _state(
                "blocked",
                vars={},
                missing_inputs=["user_message"],
                questions_to_user=["Опиши завдання, яке потрібно виконати"],
                why_blocked="Опиши завдання, яке потрібно виконати",
            )
        ]
    )
    gateway = ChatAgentGateway(engine)

    response = gateway.send_user_message("   ")

    assert response.status == "blocked"
    history = gateway.history(response.conversation_id)
    assert [msg.role for msg in history] == ["chat"]
    payload = engine.calls[0]["input"]
    assert "user_message" not in payload
    assert payload["max_reviews"] == 1


def test_chat_agent_waits_without_new_user_message() -> None:
    engine = DummyEngine(
        [
            _state(
                "blocked",
                vars={},
                missing_inputs=["user_message"],
                questions_to_user=["Опиши завдання, яке потрібно виконати"],
                why_blocked="Опиши завдання, яке потрібно виконати",
            )
        ]
    )
    gateway = ChatAgentGateway(engine)

    first = gateway.send_user_message("  ")
    second = gateway.send_user_message("", conversation_id=first.conversation_id)

    assert first.status == "blocked"
    assert second.status == "blocked"
    assert len(engine.calls) == 1
    history = gateway.history(first.conversation_id)
    assert len(history) == 1
    assert history[0].content == "Опиши завдання, яке потрібно виконати"


def test_chat_agent_survives_engine_errors() -> None:
    class ExplodingEngine(DummyEngine):
        def run_to_completion(
            self, agent_name: str, input_json: Dict[str, Any], *, raise_on_error: bool = True
        ) -> ExecutionState:
            raise RuntimeError("engine boom")

    gateway = ChatAgentGateway(ExplodingEngine([]))

    response = gateway.send_user_message("help")

    assert response.status == "error"
    assert "boom" in (response.message.content or "")
    assert response.message.status == "error"
