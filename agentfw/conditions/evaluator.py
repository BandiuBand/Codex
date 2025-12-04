from __future__ import annotations

from dataclasses import dataclass

from agentfw.core.models import ConditionDefinition
from agentfw.core.state import AgentState


@dataclass
class ConditionEvaluator:
    """Evaluates condition definitions against agent state."""

    def evaluate(self, condition: ConditionDefinition, state: AgentState) -> bool:
        """Return True when the provided condition evaluates to true."""
        if condition.type == "always":
            return True

        if condition.type == "equals":
            if condition.value_from not in state.variables:
                return False
            return state.variables[condition.value_from] == condition.value

        if condition.type == "not_equals":
            return state.variables.get(condition.value_from) != condition.value

        if condition.type == "greater_than":
            value = state.variables.get(condition.value_from)
            return value is not None and value > condition.value

        if condition.type == "less_than":
            value = state.variables.get(condition.value_from)
            return value is not None and value < condition.value

        if condition.type == "contains":
            container = state.variables.get(condition.value_from)
            try:
                return condition.value in container
            except TypeError:
                return False

        if condition.type == "expression":
            raise NotImplementedError("Expression conditions are not implemented yet")

        raise ValueError(f"Unsupported condition type: {condition.type}")


@dataclass
class ExpressionEvaluator:
    """Safely evaluates expression-based conditions."""

    def eval(self, expression: str, variables: dict[str, object]) -> bool:
        """Evaluate an expression using the given variable mapping."""
        raise NotImplementedError()
