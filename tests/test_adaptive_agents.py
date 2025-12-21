from __future__ import annotations

import json
import shutil
from pathlib import Path

from agentfw.llm.base import LLMClient
from agentfw.runtime.engine import AgentRepository, ExecutionEngine


class ScriptedLLM(LLMClient):
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate(self, prompt: str, **kwargs: object) -> str:  # noqa: ANN003
        self.calls.append({"prompt": prompt, "kwargs": kwargs})
        lowered = prompt.lower()
        if "визначи чи завдання є складним" in lowered:
            if "коротке завдання" in lowered:
                is_complex = False
            else:
                is_complex = "довге" in lowered or "дуже довге" in lowered or len(prompt) > 200
            return json.dumps({"is_complex": is_complex, "reason": "rule based"})
        if "швидка відповідь" in lowered:
            return "LLM_SIMPLE:" + prompt[:32]
        if "перевіряє готовність" in lowered or "готовність" in lowered:
            return json.dumps(
                {
                    "needs_more_info": False,
                    "clarifications": "даних достатньо",
                    "context_summary": "усі ключові параметри відомі",
                }
            )
        if "планувальник" in lowered:
            return json.dumps(
                {
                    "steps": ["Крок 1: підготувати дані", "Крок 2: виконати дію"],
                    "criteria": ["Перевірити дані", "Перевірити вихід"],
                }
            )
        if "агент-\"цербер\"" in lowered:
            return json.dumps(
                {
                    "executed_steps": [
                        {
                            "крок": "Крок 1: підготувати дані",
                            "критерій": "Перевірити дані",
                            "результат": "дані підготовлені",
                            "коментар": "ок",
                            "прийнято": True,
                            "спроб": 1,
                            "evidence": ["demo-path-1"],
                        },
                        {
                            "крок": "Крок 2: виконати дію",
                            "критерій": "Перевірити вихід",
                            "результат": "дію виконано",
                            "коментар": "ок",
                            "прийнято": True,
                            "спроб": 1,
                            "evidence": ["demo-path-2"],
                        },
                    ],
                    "passed": True,
                    "cerber_comment": "усі кроки прийнято",
                    "needs_retry": False,
                    "summary": "Усі кроки пройшли",
                }
            )
        if "підсумуй виконання" in lowered:
            return "Підсумок: успіх"
        return "LLM:" + prompt


def _engine(tmp_path: Path) -> ExecutionEngine:
    repo = AgentRepository(Path("agents"))
    scripted = ScriptedLLM()

    def factory(host: str, model: str) -> ScriptedLLM:  # noqa: ARG001
        return scripted

    return ExecutionEngine(
        repository=repo,
        runs_dir=tmp_path / "runs",
        llm_client=scripted,
        llm_client_factory=factory,
    )


def test_adaptive_agent_simple(tmp_path: Path) -> None:
    engine = _engine(tmp_path)

    state = engine.run_to_completion(
        "adaptive_task_agent",
        input_json={
            "завдання": "коротке завдання",
            "max_reviews": 2,
        },
    )

    assert state.vars["is_complex"] is False
    assert "LLM_SIMPLE" in state.vars["фінальна_відповідь"]
    assert "швидка_відповідь" in state.vars


def test_adaptive_agent_complex(tmp_path: Path) -> None:
    engine = _engine(tmp_path)

    long_task = "Це дуже довге формулювання задачі, яке однозначно складніше за короткий запит."
    state = engine.run_to_completion(
        "adaptive_task_agent",
        input_json={
            "завдання": long_task,
            "max_reviews": 3,
        },
    )

    assert state.vars["is_complex"] is True
    assert state.vars["пройшло_перевірку"] is True
    assert state.vars["кроки"] == ["Крок 1: підготувати дані", "Крок 2: виконати дію"]
    assert state.vars["критерії"][0].startswith("Перевірити")
    assert "Підсумок" in state.vars["фінальна_відповідь"]


def test_workspace_file_agents(tmp_path: Path) -> None:
    workspace = Path("agent_workspace")
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)

    engine = _engine(tmp_path)

    write_state = engine.run_to_completion(
        "workspace_write_file", input_json={"шлях": "notes/demo.txt", "вміст": "hello world"}
    )
    assert "notes/demo.txt" in write_state.vars["результат"]

    read_state = engine.run_to_completion("workspace_read_file", input_json={"шлях": "notes/demo.txt"})
    assert read_state.vars["вміст"] == "hello world"

    list_state = engine.run_to_completion("workspace_list_files", input_json={})
    assert "notes/demo.txt" in list_state.vars["файли"]
