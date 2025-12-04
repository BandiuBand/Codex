from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
import time

from agentfw.conditions.evaluator import ConditionEvaluator
from agentfw.core.models import StepDefinition
from agentfw.core.registry import AgentRegistry, ToolRegistry
from agentfw.core.state import AgentState, ExecutionContext, StepExecutionRecord
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
        definition = self.agent_registry.get(agent_name)

        state = AgentState(
            run_id=str(int(time.time() * 1000)),
            agent_name=agent_name,
            current_step_id=definition.entry_step_id,
            finished=False,
            failed=False,
            variables=dict(input_json),
            history=[],
        )

        if definition.serialize_enabled:
            self.storage.save_state(state)

        return state

    def resume_run(self, state: AgentState) -> AgentState:
        """Resume agent execution from the current step."""
        definition = self.agent_registry.get(state.agent_name)

        while not state.finished and not state.failed:
            ctx = ExecutionContext(definition=definition, state=state, engine=self)
            self._execute_next_step(ctx)

            if definition.serialize_enabled:
                self.storage.save_state(state)

        return state

    def run_to_completion(self, agent_name: str, input_json: Dict[str, object]) -> AgentState:
        """Convenience method to start and run an agent until it finishes."""
        state = self.start_run(agent_name, input_json)
        state = self.resume_run(state)
        return state

    def _execute_next_step(self, ctx: ExecutionContext) -> None:
        """Execute the next step in the agent definition."""
        if not ctx.state.current_step_id:
            ctx.state.finished = True
            return

        step_def = ctx.definition.get_step(ctx.state.current_step_id)

        input_snapshot = dict(ctx.state.variables)

        tool_result: Dict[str, object] | None = None
        validator_result: Dict[str, object] | None = None
        error: str | None = None
        started_at = time.time()

        if step_def.tool_name is not None:
            try:
                tool = self.tool_registry.get(step_def.tool_name)
                tool_result = tool.execute(ctx, step_def.tool_params)
            except Exception as exc:  # noqa: BLE001
                error = str(exc)
                ctx.state.failed = True

        finished_at = time.time()

        record = StepExecutionRecord(
            step_id=step_def.id,
            started_at=started_at,
            finished_at=finished_at,
            input_variables_snapshot=input_snapshot,
            tool_result=tool_result,
            validator_result=validator_result,
            chosen_transition=None,
            error=error,
        )

        if error is not None:
            ctx.state.history.append(record)
            if ctx.definition.serialize_enabled:
                self.storage.save_step_record(ctx.state, record)
            ctx.state.failed = True
            return

        for var_name, result_key in step_def.save_mapping.items():
            if tool_result and result_key in tool_result:
                ctx.state.variables[var_name] = tool_result[result_key]

        next_step_id = self._choose_transition(ctx, step_def, tool_result, validator_result)
        record.chosen_transition = next_step_id

        if next_step_id is None:
            ctx.state.current_step_id = ""
            ctx.state.finished = True
        else:
            ctx.state.current_step_id = next_step_id

        ctx.state.history.append(record)
        if ctx.definition.serialize_enabled:
            self.storage.save_step_record(ctx.state, record)

    def _choose_transition(
        self,
        ctx: ExecutionContext,
        step_def: StepDefinition,
        tool_result: Dict[str, object] | None,
        validator_result: Dict[str, object] | None,
    ) -> str | None:
        """Select the target step id using transitions and the condition evaluator."""
        for transition in step_def.transitions:
            cond = transition.condition
            if self.condition_evaluator.evaluate(cond, ctx.state):
                return transition.target_step_id

        return None
