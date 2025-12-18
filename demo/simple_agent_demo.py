from __future__ import annotations

from pathlib import Path
import sys

from agentfw.llm.base import DummyLLMClient
from agentfw.runtime.engine import AgentRepository, ExecutionEngine

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _dummy_llm_factory(host: str, model: str) -> DummyLLMClient:
    prefix = f"LLM({model})@{host}: "
    return DummyLLMClient(prefix=prefix)


def build_engine() -> ExecutionEngine:
    repo = AgentRepository(ROOT_DIR / "agents")
    return ExecutionEngine(repository=repo, runs_dir=ROOT_DIR / "runs", llm_client_factory=_dummy_llm_factory)


def run_llm_workflow(engine: ExecutionEngine) -> None:
    payload = {
        "користувацький_запит": "Привіт, Codex! Опиши головну ідею системи.",
        "ollama_host": "http://127.0.0.1:11434",
        "ollama_model": "llama3",
        "temperature": 0.2,
    }
    state = engine.run_to_completion("llm_prompt_chain", input_json=payload)
    print("LLM chain finished:", state.vars.get("відповідь"))


def run_branching_demo(engine: ExecutionEngine) -> None:
    state = engine.run_to_completion("workflow_demo", input_json={"task_text": "коротке завдання"})
    print("Workflow demo відповідь:", state.vars.get("відповідь"))


def main() -> None:
    engine = build_engine()
    run_llm_workflow(engine)
    run_branching_demo(engine)


if __name__ == "__main__":
    main()
