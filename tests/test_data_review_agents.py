from pathlib import Path

from agentfw.llm.base import LLMClient
from agentfw.runtime.engine import AgentRepository, ExecutionEngine


class StubLLM(LLMClient):
    def __init__(self, outputs: list[str]):
        self.outputs = list(outputs)
        self.calls: list[dict[str, object]] = []

    def generate(self, prompt: str, **kwargs: object) -> str:  # noqa: ANN003
        self.calls.append({"prompt": prompt, "kwargs": kwargs})
        if not self.outputs:
            raise AssertionError("No scripted responses left")
        return self.outputs.pop(0)


def _engine(tmp_path: Path, llm: StubLLM) -> ExecutionEngine:
    def factory(host: str, model: str) -> StubLLM:  # noqa: ARG001
        return llm

    return ExecutionEngine(
        repository=AgentRepository(Path("agents")),
        runs_dir=tmp_path / "runs",
        llm_client=llm,
        llm_client_factory=factory,
    )


def test_data_review_handles_invalid_json(tmp_path: Path) -> None:
    llm = StubLLM(["This is not JSON and should fail parsing"])
    engine = _engine(tmp_path, llm)

    state = engine.run_to_completion(
        "data_review",
        input_json={"завдання": "тестуємо помилковий вивід"},
        raise_on_error=False,
    )

    assert state.vars["ok"] is False
    assert state.vars["needs_more_info"] is False
    assert state.vars["clarifications"] == ""
    assert state.vars["context_summary"] == ""
    assert state.vars["json_error"]


def test_data_review_maps_valid_review(tmp_path: Path) -> None:
    llm = StubLLM(
        [
            """
            {"data_review": {
                "ok": false,
                "needs_more_info": true,
                "clarifications": "Уточни цілі",
                "context_summary": "Є попередні дані",
                "user_answer": "користувач відповів"
            }}
            """
        ]
    )
    engine = _engine(tmp_path, llm)

    state = engine.run_to_completion(
        "data_review",
        input_json={"завдання": "приклад валідного результату"},
        raise_on_error=False,
    )

    assert state.vars["ok"] is False
    assert state.vars["needs_more_info"] is True
    assert state.vars["clarifications"] == "Уточни цілі"
    assert state.vars["context_summary"] == "Є попередні дані"
    assert state.vars["user_answer"] == "користувач відповів"
    assert not state.vars.get("json_error")
