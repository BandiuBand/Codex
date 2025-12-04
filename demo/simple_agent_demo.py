from __future__ import annotations

from pathlib import Path
import sys

# Ensure repository root is on PYTHONPATH for direct execution
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agentfw.conditions.evaluator import ConditionEvaluator
from agentfw.core.registry import AgentRegistry, ToolRegistry
from agentfw.llm.base import DummyLLMClient
from agentfw.persistence.storage import FileRunStorage
from agentfw.runtime.engine import ExecutionEngine
from agentfw.tools.builtin import EchoTool, MathAddTool, LLMTool


# Tool registry with built-in demo tools
# These names are referenced in StepDefinition.tool_name
# to execute the corresponding tool implementations.
tool_registry = ToolRegistry(tools={})
tool_registry.register("echo", EchoTool())
tool_registry.register("math_add", MathAddTool())
tool_registry.register("llm", LLMTool(client=DummyLLMClient()))


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


if __name__ == "__main__":
    main()
