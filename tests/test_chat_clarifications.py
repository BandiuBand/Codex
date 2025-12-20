import json

from agentfw.llm.base import LLMClient
from agentfw.runtime.engine import ExecutionEngine


class QueueLLM(LLMClient):
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)

    def generate(self, prompt: str, **kwargs: object) -> str:  # noqa: ARG002
        if not self.responses:
            raise AssertionError("No responses left for prompt: " + prompt)
        return self.responses.pop(0)


def test_adaptive_agent_blocks_to_collect_clarifications_via_chat() -> None:
    responses = [
        json.dumps({"is_complex": True, "reason": "needs more data"}),
        json.dumps({"needs_more_info": True, "clarifications": "Уточніть деталі", "context_summary": ""}),
    ]
    queue_llm = QueueLLM(responses)
    engine = ExecutionEngine(llm_client=queue_llm)

    state = engine.run_to_completion(
        "adaptive_task_agent",
        {"user_message": "Потрібен план поєднання даних", "max_reviews": 1},
        raise_on_error=False,
    )

    assert state.status == "blocked"
    assert state.questions_to_user == ["Уточніть деталі"]
    assert state.missing_inputs in (None, []) or "user_message" in state.missing_inputs
    assert queue_llm.responses == []


def test_adaptive_agent_blocks_initially_when_no_task_provided() -> None:
    engine = ExecutionEngine()

    state = engine.run_to_completion("adaptive_task_agent", input_json={}, raise_on_error=False)

    assert state.status == "blocked"
    assert state.missing_inputs in (None, [])
    assert state.questions_to_user == ["Опиши завдання, яке потрібно виконати"]
