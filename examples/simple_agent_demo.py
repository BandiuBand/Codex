from __future__ import annotations

from pathlib import Path

from agentfw.conditions.evaluator import ConditionEvaluator, ExpressionEvaluator
from agentfw.core.models import (
    AgentDefinition,
    ConditionDefinition,
    StepDefinition,
    TransitionDefinition,
)
from agentfw.core.registry import AgentRegistry, ToolRegistry
from agentfw.persistence.storage import FileRunStorage
from agentfw.runtime.engine import ExecutionEngine
from agentfw.tools.builtin import EchoTool, FlakyTool, MathAddTool


DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "runs"

# Tool registry with built-in demo tools
# These names are referenced in StepDefinition.tool_name
# to execute the corresponding tool implementations.
tool_registry = ToolRegistry(tools={})
tool_registry.register("echo", EchoTool())
tool_registry.register("math_add", MathAddTool())
tool_registry.register("flaky", FlakyTool())

# Step definitions
init_step = StepDefinition(
    id="init",
    name="Init variables",
    kind="tool",
    tool_name=None,
    tool_params={},
    save_mapping={},
    validator_agent_name=None,
    validator_params={},
    validator_policy={},
    transitions=[
        TransitionDefinition(
            target_step_id="sum_step",
            condition=ConditionDefinition(
                type="always",
                value_from=None,
                value=None,
                expression=None,
                extra={},
            ),
        )
    ],
)

sum_step = StepDefinition(
    id="sum_step",
    name="Compute sum",
    kind="tool",
    tool_name="math_add",
    tool_params={"a_var": "x", "b_var": "y"},
    save_mapping={"sum": "result"},
    validator_agent_name=None,
    validator_params={},
    validator_policy={},
    transitions=[
        TransitionDefinition(
            target_step_id="branch_step",
            condition=ConditionDefinition(
                type="always",
                value_from=None,
                value=None,
                expression=None,
                extra={},
            ),
        )
    ],
)

branch_step = StepDefinition(
    id="branch_step",
    name="Branch on sum",
    kind="tool",
    tool_name=None,
    tool_params={},
    save_mapping={},
    validator_agent_name=None,
    validator_params={},
    validator_policy={},
    transitions=[
        TransitionDefinition(
            target_step_id="big",
            condition=ConditionDefinition(
                type="greater_than",
                value_from="sum",
                value=10,
                expression=None,
                extra={},
            ),
        ),
        TransitionDefinition(
            target_step_id="small",
            condition=ConditionDefinition(
                type="always",
                value_from=None,
                value=None,
                expression=None,
                extra={},
            ),
        ),
    ],
)

big_step = StepDefinition(
    id="big",
    name="Big sum",
    kind="tool",
    tool_name="echo",
    tool_params={"text": "Sum {sum} is BIG"},
    save_mapping={"message": "output_text"},
    validator_agent_name=None,
    validator_params={},
    validator_policy={},
    transitions=[],
)

small_step = StepDefinition(
    id="small",
    name="Small sum",
    kind="tool",
    tool_name="echo",
    tool_params={"text": "Sum {sum} is small"},
    save_mapping={"message": "output_text"},
    validator_agent_name=None,
    validator_params={},
    validator_policy={},
    transitions=[],
)

agent_def = AgentDefinition(
    name="simple_demo_agent",
    description="Simple demo agent with sum and branching.",
    input_schema=None,
    output_schema=None,
    steps={
        "init": init_step,
        "sum_step": sum_step,
        "branch_step": branch_step,
        "big": big_step,
        "small": small_step,
    },
    entry_step_id="init",
    end_step_ids={"big", "small"},
    serialize_enabled=True,
    serialize_base_dir=str(DATA_DIR),
    serialize_per_step=True,
)


def main() -> None:
    agent_registry = AgentRegistry(agents={}, config_dirs=[])
    agent_registry.register(agent_def)

    storage = FileRunStorage(base_dir=str(DATA_DIR))
    condition_evaluator = ConditionEvaluator(expression_evaluator=ExpressionEvaluator())
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


if __name__ == "__main__":
    main()
