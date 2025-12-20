from agentfw.runtime.engine import ExecutionEngine


def test_chat_agent_blocks_until_user_message():
    engine = ExecutionEngine()

    state = engine.run_to_completion(
        "chat_agent",
        {"message_to_user": "Дай задачу", "needs_response": True, "user_message": None},
        raise_on_error=False,
    )

    assert state.status == "blocked"
    assert state.missing_inputs == ["user_message"]
    assert state.questions_to_user == ["Дай задачу"]


def test_chat_agent_passes_through_user_message():
    engine = ExecutionEngine()

    state = engine.run_to_completion(
        "chat_agent",
        {"message_to_user": "Дякую", "needs_response": False, "user_message": "готово"},
    )

    assert state.status == "ok"
    assert state.vars.get("user_message") == "готово"
