import pytest

from agentfw.runtime.chat_agent import ChatAgentGateway


def test_agent_messages_saved_without_ui() -> None:
    chat = ChatAgentGateway()

    first = chat.post_agent("AdaptiveAgent", "Привіт, дай задачу")

    assert first.role == "agent"
    assert chat.history()[-1].text == "Привіт, дай задачу"


def test_chat_waits_for_real_user_reply() -> None:
    chat = ChatAgentGateway()
    chat.ask_user("AdaptiveAgent", "Опиши задачу")

    chat.post_user("Намалюй план")
    answer = chat.wait_user()

    assert answer == "Намалюй план"


def test_wait_user_times_out_without_pending_question() -> None:
    chat = ChatAgentGateway()

    with pytest.raises(RuntimeError):
        chat.wait_user(timeout=0.01)


def test_blank_messages_rejected() -> None:
    chat = ChatAgentGateway()

    with pytest.raises(ValueError):
        chat.post_user("   ")

    with pytest.raises(ValueError):
        chat.post_agent("any", "")

