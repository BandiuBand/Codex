import json

import pytest

from agentfw.llm.base import LLMClient
from agentfw.runtime.engine import ExecutionEngine


class JsonLLM(LLMClient):
    def __init__(self, payload: str) -> None:
        self.payload = payload

    def generate(self, prompt: str, **kwargs: object) -> str:  # noqa: ARG002
        return self.payload


def test_task_classifier_marks_file_tasks_complex():
    llm_payload = json.dumps({"is_complex": True, "reason": "needs repository access"})
    engine = ExecutionEngine(llm_client=JsonLLM(llm_payload))

    state = engine.run_to_completion("task_classifier", {"task_text": "Прочитай код у репозиторії"})

    assert state.vars.get("is_complex") is True
    assert "repository" in (state.vars.get("класифікація") or "")


def test_simple_answer_blocks_file_requests():
    engine = ExecutionEngine()

    state = engine.run_to_completion("llm_simple_answer", {"task_text": "Прочитай файл README"})

    assert state.status == "blocked"
    assert state.why_blocked
    assert state.missing_inputs is not None


def test_llm_simple_answer_llm_propagates_blocked_status():
    blocked_json = json.dumps(
        {
            "llm_simple_answer": {
                "status": "blocked",
                "missing_inputs": ["додатковий контекст"],
                "questions_to_user": ["Що саме треба з'ясувати?"],
                "why_blocked": "Немає фактів для відповіді",
            }
        }
    )
    engine = ExecutionEngine(llm_client=JsonLLM(blocked_json))

    state = engine.run_to_completion("llm_simple_answer_llm", {"task_text": "Питання"})

    assert state.status == "blocked"
    assert state.missing_inputs == ["додатковий контекст"]
    assert state.questions_to_user == ["Що саме треба з'ясувати?"]
    assert state.why_blocked == "Немає фактів для відповіді"
