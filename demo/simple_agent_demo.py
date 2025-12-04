from __future__ import annotations

from pathlib import Path
import sys

# Ensure repository root is on PYTHONPATH for direct execution
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agentfw.conditions.evaluator import ConditionEvaluator
from agentfw.config.settings import LLMConfig
from agentfw.core.registry import AgentRegistry, ToolRegistry
from agentfw.llm.base import DummyLLMClient, OllamaLLMClient
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


llm_config = LLMConfig.from_env()

if llm_config.backend == "ollama":
    llm_client = OllamaLLMClient(
        base_url=llm_config.base_url or "http://localhost:11434",
        model=llm_config.model or "qwen3:32b",
        api_key=llm_config.api_key,
    )
else:
    # fallback по замовчуванню
    llm_client = DummyLLMClient()


# Tool registry with built-in demo tools
# These names are referenced in StepDefinition.tool_name
# to execute the corresponding tool implementations.
tool_registry = ToolRegistry(tools={})
tool_registry.register("echo", EchoTool())
tool_registry.register("math_add", MathAddTool())
tool_registry.register("llm", LLMTool(client=llm_client))
tool_registry.register("cerber_accept", AcceptValidatorTool())
tool_registry.register("flaky", FlakyTool())
tool_registry.register("retry_validator", AttemptThresholdValidatorTool())
tool_registry.register("shell", ShellTool())


def main() -> None:
    agents_dir = ROOT_DIR / "agents"

    agent_registry = AgentRegistry(
        agents={},
        config_dirs=[str(agents_dir)],
    )
    agent_registry.load_all()

    storage = FileRunStorage(base_dir="./data/runs")
    condition_evaluator = ConditionEvaluator()
    engine = ExecutionEngine(
        agent_registry=agent_registry,
        tool_registry=tool_registry,
        storage=storage,
        condition_evaluator=condition_evaluator,
    )

    # Register AgentCallTool after the engine is created to avoid circular dependency
    tool_registry.register("agent_call", AgentCallTool(engine=engine))

    state_shell = engine.run_to_completion(
        agent_name="shell_demo_agent",
        input_json={},
    )
    print("Shell demo variables:", state_shell.variables)

    state1 = engine.run_to_completion(
        agent_name="simple_demo_agent",
        input_json={"x": 3, "y": 4},
    )
    print("Run 1 variables:", state1.variables)

    state2 = engine.run_to_completion(
        agent_name="simple_demo_agent",
        input_json={"x": 10, "y": 5},
    )
    print("Run 2 variables:", state2.variables)

    state_llm = engine.run_to_completion(
        agent_name="llm_demo_agent",
        input_json={"user_name": "Bandiu"},
    )
    print("LLM demo variables:", state_llm.variables)

    state_parent = engine.run_to_completion(
        agent_name="parent_demo_agent",
        input_json={"x": 3, "y": 4},
    )
    print("Parent demo variables:", state_parent.variables)

    state_flaky = engine.run_to_completion(
        agent_name="flaky_retry_demo_agent",
        input_json={},
    )
    print(
        "Flaky retry variables:",
        state_flaky.variables,
        "history entries:",
        len(state_flaky.history),
    )

    state_flaky_fail = engine.run_to_completion(
        agent_name="flaky_failure_demo_agent",
        input_json={},
    )
    print(
        "Flaky failure variables:",
        state_flaky_fail.variables,
        "failed:",
        state_flaky_fail.failed,
        "history entries:",
        len(state_flaky_fail.history),
    )


if __name__ == "__main__":
    main()
