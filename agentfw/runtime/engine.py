from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from agentfw.conditions.evaluator import ConditionEvaluator
from agentfw.core.models import StepDefinition
from agentfw.core.registry import AgentRegistry, ToolRegistry
from agentfw.core.state import AgentState, ExecutionContext
from agentfw.persistence.storage import RunStorage


@dataclass
class ExecutionEngine:
    """Core execution engine orchestrating agent runs."""

    agent_registry: AgentRegistry
    tool_registry: ToolRegistry
    storage: RunStorage
    condition_evaluator: ConditionEvaluator

    def start_run(self, agent_name: str, input_json: Dict[str, object]) -> AgentState:
        """Create a new agent state and initialize starting variables."""
        raise NotImplementedError()

    def resume_run(self, state: AgentState) -> AgentState:
        """Resume agent execution from the current step."""
        raise NotImplementedError()

    def run_to_completion(self, agent_name: str, input_json: Dict[str, object]) -> AgentState:
        """Convenience method to start and run an agent until it finishes."""
        raise NotImplementedError()

    def _execute_next_step(self, ctx: ExecutionContext) -> None:
        """Execute the next step in the agent definition."""
        raise NotImplementedError()

    def _choose_transition(
        self,
        ctx: ExecutionContext,
        step_def: StepDefinition,
        tool_result: Dict[str, object] | None,
        validator_result: Dict[str, object] | None,
    ) -> str | None:
        """Select the target step id using transitions and the condition evaluator."""
        raise NotImplementedError()
