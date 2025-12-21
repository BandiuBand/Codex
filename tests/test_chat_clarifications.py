import json
import threading
import time

from agentfw.llm.base import LLMClient
from agentfw.runtime.engine import ExecutionEngine
from tests.test_adaptive_agents import ScriptedLLM


class QueueLLM(LLMClient):
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self._last = responses[0] if responses else json.dumps({"result": "ok"})

    def generate(self, prompt: str, **kwargs: object) -> str:  # noqa: ARG002
        if self.responses:
            self._last = self.responses.pop(0)
        return self._last


def test_adaptive_agent_waits_until_user_provides_initial_task() -> None:
    scripted = ScriptedLLM()
    engine = ExecutionEngine(llm_client=scripted)
    result: dict[str, object] = {}

    def run_agent() -> None:
        result["state"] = engine.run_to_completion(
            "adaptive_task_agent", input_json={}, raise_on_error=False
        )

    thread = threading.Thread(target=run_agent)
    thread.start()
    time.sleep(0.1)

    assert thread.is_alive()
    assert scripted.calls == []

    engine.chat_gateway.post_user("коротке завдання")
    thread.join(timeout=2)

    state = result["state"]
    assert state.status == "ok"
    assert state.vars["user_message"] == "коротке завдання"
    assert scripted.calls  # виклик LLM відбувся вже після відповіді користувача


def test_adaptive_agent_waits_for_clarification_and_resumes() -> None:
    responses = [
        json.dumps({"is_complex": True, "reason": "needs more data"}),
        json.dumps({"needs_more_info": True, "clarifications": "Уточніть деталі", "context_summary": ""}),
        json.dumps({"plan_json": "[]", "кроки": [], "фінальна_відповідь": "done"}),
    ]
    queue_llm = QueueLLM(responses)
    engine = ExecutionEngine(llm_client=queue_llm)
    result: dict[str, object] = {}

    def run_agent() -> None:
        result["state"] = engine.run_to_completion(
            "adaptive_task_agent",
            {"user_message": "Потрібен план поєднання даних", "max_reviews": 1},
            raise_on_error=False,
        )

    thread = threading.Thread(target=run_agent)
    thread.start()
    time.sleep(0.1)
    assert thread.is_alive()

    engine.chat_gateway.post_user("Ось уточнення")
    thread.join(timeout=3)

    state = result["state"]
    assert state.status == "ok"
    assert queue_llm.responses == []
