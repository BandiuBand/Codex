from agentfw.conditions.evaluator import ConditionEvaluator
from agentfw.core.models import ConditionDefinition
from agentfw.core.state import AgentState


def make_state(**variables: object) -> AgentState:
    return AgentState(
        run_id="test",
        agent_name="agent",
        variables=variables,
    )


def test_greater_than_uses_right_variable() -> None:
    condition = ConditionDefinition(
        type="greater_than", value_from="left", right_var="right"
    )
    evaluator = ConditionEvaluator()

    assert evaluator.evaluate(condition, make_state(left=5, right=3)) is True
    assert evaluator.evaluate(condition, make_state(left=1, right=3)) is False
    assert evaluator.evaluate(condition, make_state(left=5)) is False


def test_less_than_falls_back_to_literal_value() -> None:
    condition = ConditionDefinition(type="less_than", value_from="metric", value=10)
    evaluator = ConditionEvaluator()

    assert evaluator.evaluate(condition, make_state(metric=5)) is True
    assert evaluator.evaluate(condition, make_state(metric=12)) is False
