from dataclasses import dataclass
from typing import Dict

from agentfw.conditions.evaluator import ConditionEvaluator
from agentfw.core.models import AgentDefinition, StepDefinition
from agentfw.core.registry import AgentRegistry, ToolRegistry
from agentfw.core.state import ExecutionContext
from agentfw.persistence.storage import RunStorage
from agentfw.runtime.engine import ExecutionEngine
from agentfw.tools.base import BaseTool


class DummyTool(BaseTool):
    def __init__(self, payload: Dict[str, object]):
        self.payload = payload

    def execute(self, ctx: ExecutionContext, params: Dict[str, object]) -> Dict[str, object]:
        return dict(self.payload)


@dataclass
class DummyStorage(RunStorage):
    def save_state(self, state):  # type: ignore[override]
        return None

    def load_state(self, run_id):  # type: ignore[override]
        raise NotImplementedError

    def save_step_record(self, state, record):  # type: ignore[override]
        return None


def test_save_mapping_supports_nested_paths() -> None:
    tool_result = {
        "output_text": "hello",
        "parsed_json": {
            "decision": "accept",
            "data": {"score": 0.95},
        },
    }

    tool_registry = ToolRegistry()
    tool_registry.register("dummy", DummyTool(tool_result))

    agent_registry = AgentRegistry()

    step_def = StepDefinition(
        id="step-1",
        tool_name="dummy",
        tool_params={},
        save_mapping={
            "var1": "output_text",
            "decision": "parsed_json.decision",
            "score": "parsed_json.data.score",
            "missing": "parsed_json.data.missing",
        },
        transitions=[],
    )

    agent_def = AgentDefinition(
        name="agent",
        steps={"step-1": step_def},
        entry_step_id="step-1",
    )
    agent_registry.register(agent_def)

    engine = ExecutionEngine(
        agent_registry=agent_registry,
        tool_registry=tool_registry,
        storage=DummyStorage(),
        condition_evaluator=ConditionEvaluator(),
    )

    state = engine.start_run("agent", {})
    ctx = ExecutionContext(definition=agent_def, state=state, engine=engine)
    engine._execute_next_step(ctx)

    assert state.variables["var1"] == "hello"
    assert state.variables["decision"] == "accept"
    assert state.variables["score"] == 0.95
    assert "missing" not in state.variables
