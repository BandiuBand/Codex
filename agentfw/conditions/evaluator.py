from __future__ import annotations

from dataclasses import dataclass

from agentfw.core.models import ConditionDefinition
from agentfw.core.state import AgentState


@dataclass
class ConditionEvaluator:
    """Evaluates condition definitions against agent state."""

    def evaluate(self, condition: ConditionDefinition, state: AgentState) -> bool:
        """Return True when the provided condition evaluates to true."""
        raise NotImplementedError()


@dataclass
class ExpressionEvaluator:
    """Safely evaluates expression-based conditions."""

    def eval(self, expression: str, variables: dict[str, object]) -> bool:
        """Evaluate an expression using the given variable mapping."""
        raise NotImplementedError()
