from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

from agentfw.conditions.evaluator import ConditionEvaluator, ExpressionEvaluator
from agentfw.config.settings import LLMConfig
from agentfw.core.registry import AgentRegistry, ToolRegistry
from agentfw.llm.base import DummyLLMClient, LLMClient, OllamaLLMClient
from agentfw.persistence.storage import FileRunStorage
from agentfw.runtime.engine import ExecutionEngine
from agentfw.tools.builtin import (
    AcceptValidatorTool,
    AgentCallTool,
    AttemptThresholdValidatorTool,
    EchoTool,
    FlakyTool,
    LLMTool,
    MathAddTool,
    ShellTool,
)


def find_agents_dir() -> Path:
    env_dir = os.environ.get("AGENTFW_AGENTS_DIR")
    if env_dir:
        return Path(env_dir)

    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        candidate = parent / "agents"
        if candidate.exists() and candidate.is_dir():
            return candidate

    project_root = Path(__file__).resolve().parents[2]
    return project_root / "agents"


def llm_client_from_env() -> LLMClient:
    llm_config = LLMConfig.from_env()
    if llm_config.backend == "ollama":
        print(
            f"[agentfw] Використовуємо Ollama (base_url={llm_config.base_url}, model={llm_config.model})"
        )
        return OllamaLLMClient(
            base_url=llm_config.base_url or "http://localhost:11434",
            model=llm_config.model or "qwen3:32b",
            api_key=llm_config.api_key,
        )
    if llm_config.backend == "dummy":
        print("[agentfw] Використовується DummyLLMClient (бекенд не налаштовано)")
        return DummyLLMClient()

    raise ValueError(
        f"Невідомий LLM backend '{llm_config.backend}'. Підтримується: dummy, ollama"
    )


def build_default_engine() -> Tuple[ExecutionEngine, AgentRegistry]:
    agents_dir = find_agents_dir()

    agent_registry = AgentRegistry(agents={}, config_dirs=[str(agents_dir)])
    agent_registry.load_all()

    tool_registry = ToolRegistry(tools={})
    tool_registry.register("echo", EchoTool())
    tool_registry.register("math_add", MathAddTool())
    tool_registry.register("llm", LLMTool(client=llm_client_from_env()))
    tool_registry.register("shell", ShellTool())
    tool_registry.register("flaky", FlakyTool())
    tool_registry.register(
        "attempt_threshold_validator", AttemptThresholdValidatorTool()
    )
    tool_registry.register("accept_validator", AcceptValidatorTool())
    tool_registry.register("cerber_accept", AcceptValidatorTool())

    storage = FileRunStorage(base_dir="./data/runs")
    expression_evaluator = ExpressionEvaluator()
    condition_evaluator = ConditionEvaluator(expression_evaluator=expression_evaluator)
    engine = ExecutionEngine(
        agent_registry=agent_registry,
        tool_registry=tool_registry,
        storage=storage,
        condition_evaluator=condition_evaluator,
    )

    tool_registry.register("agent_call", AgentCallTool(engine=engine))

    return engine, agent_registry
