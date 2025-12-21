import threading
import time

from agentfw.runtime.engine import ExecutionEngine


def test_chat_agent_waits_synchronously_until_user_message():
    engine = ExecutionEngine()
    result: dict[str, object] = {}

    def run_agent() -> None:
        result["state"] = engine.run_to_completion(
            "chat_agent",
            {"message_to_user": "Дай задачу", "needs_response": True, "user_message": None},
            raise_on_error=False,
        )

    thread = threading.Thread(target=run_agent)
    thread.start()
    time.sleep(0.1)
    assert thread.is_alive()

    engine.chat_gateway.post_user("конкретне завдання")
    thread.join(timeout=2)

    assert "state" in result
    state = result["state"]
    assert state.status == "ok"
    assert state.vars.get("user_message") == "конкретне завдання"


def test_chat_agent_passes_through_user_message():
    engine = ExecutionEngine()

    state = engine.run_to_completion(
        "chat_agent",
        {"message_to_user": "Дякую", "needs_response": False, "user_message": "готово"},
    )

    assert state.status == "ok"
    assert state.vars.get("user_message") == "готово"
