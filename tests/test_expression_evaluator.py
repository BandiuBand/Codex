import pytest

from agentfw.conditions.evaluator import ConditionEvaluator, ExpressionEvaluator
from agentfw.core.models import ConditionDefinition
from agentfw.core.state import AgentState


def make_state(**variables: object) -> AgentState:
    return AgentState(
        run_id="test",
        agent_name="agent",
        variables=variables,
    )


def test_expression_evaluator_allows_whitelisted_operations() -> None:
    evaluator = ExpressionEvaluator()
    variables = {"score": 12, "tag": "ok", "items": ["a", "b"]}

    assert evaluator.eval("score > 10 and tag == 'ok' and 'a' in items", variables)


def test_expression_evaluator_blocks_calls_and_dunders() -> None:
    evaluator = ExpressionEvaluator()

    with pytest.raises(ValueError):
        evaluator.eval("danger()", {})

    with pytest.raises(ValueError):
        evaluator.eval("value.__class__", {"value": 1})


def test_expression_evaluator_supports_not_and_extended_comparisons() -> None:
    evaluator = ExpressionEvaluator()
    variables = {"score": 5, "tags": ["x", "z"], "flag": False}

    assert evaluator.eval("not flag and score >= 5 and 'y' not in tags", variables)
    assert evaluator.eval("-1 < score <= 5", variables)

    with pytest.raises(ValueError):
        evaluator.eval("~score", variables)


def test_condition_evaluator_handles_expression_errors() -> None:
    condition = ConditionDefinition(type="expression", expression="missing_var > 1")
    state = make_state(existing=1)
    evaluator = ConditionEvaluator(expression_evaluator=ExpressionEvaluator())

    assert evaluator.evaluate(condition, state) is False
