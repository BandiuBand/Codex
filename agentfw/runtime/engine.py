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
            retry_counts={},
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
        """Execute the next step in the agent definition.

        The execution flow is intentionally documented for downstream tooling (e.g.
        frontend run visualizers):
        1. Resolve the step definition and take a snapshot of the current
           variables so we can record what the tool saw, even if later steps mutate
           the state.
        2. If a tool is configured, fetch it from the registry and execute it with
           ``tool_params``. Any exception marks the run failed and is captured on
           the execution record.
        3. Persist selected outputs back into ``state.variables`` according to the
           step's ``save_mapping`` (only keys present in the tool result are
           copied).
        4. When a validator agent is declared, call it with a payload that includes
           input/output snapshots and retry metadata. The validator policy controls
           retry attempts; a "retry" status short-circuits the step (recording a
           history entry without a transition) so it can be re-run, while "fail"
           marks the state failed. Accepted validations may optionally patch
           variables before continuing.
        5. Choose the next transition using ``_choose_transition`` and the current
           state (which may include validator patches). "None" means terminal and
           sets ``finished``.
        6. Append a ``StepExecutionRecord`` to ``state.history`` (and persisted
           storage when enabled) containing the input snapshot, tool/validator
           outputs, chosen transition, timestamps, and any error string so the
           entire step lifecycle is auditable.
        """
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

        if error is not None:
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
            ctx.state.history.append(record)
            if ctx.definition.serialize_enabled:
                self.storage.save_step_record(ctx.state, record)
            ctx.state.failed = True
            return

        for var_name, result_key in step_def.save_mapping.items():
            if tool_result and result_key in tool_result:
                ctx.state.variables[var_name] = tool_result[result_key]

        if step_def.validator_agent_name:
            retry_counts = ctx.state.retry_counts
            attempt = retry_counts.get(step_def.id, 0) + 1
            validator_input = {
                "run_id": ctx.state.run_id,
                "agent_name": ctx.state.agent_name,
                "step_id": step_def.id,
                "step_name": step_def.name,
                "tool_name": step_def.tool_name,
                "attempt": attempt,
                "input_variables": input_snapshot,
                "output_variables": dict(ctx.state.variables),
                "tool_result": tool_result or {},
                "validator_params": step_def.validator_params or {},
            }

            validator_state = self.run_to_completion(
                agent_name=step_def.validator_agent_name,
                input_json=validator_input,
            )

            validation_payload = validator_state.variables.get("validation", {})
            if not isinstance(validation_payload, dict):
                validation_payload = {}

            validator_result = validation_payload

            status_raw = validation_payload.get("status")
            status = str(status_raw).lower() if status_raw is not None else ""
            message = str(validation_payload.get("message", ""))
            patch = validation_payload.get("patch")

            max_retries_raw = step_def.validator_policy.get("max_retries", "0")
            try:
                max_retries = int(max_retries_raw) if max_retries_raw is not None else 0
            except (TypeError, ValueError):
                max_retries = 0

            retry_counts[step_def.id] = attempt

            if validator_state.failed:
                status = "fail"
                if not message:
                    message = "validator agent failed"

            if not status:
                status = "fail"
                if not message:
                    message = "validator did not return a status"

            if status == "accept":
                if isinstance(patch, dict):
                    ctx.state.variables.update(patch)
            elif status == "retry":
                if attempt <= max_retries:
                    finished_at = time.time()
                    record = StepExecutionRecord(
                        step_id=step_def.id,
                        started_at=started_at,
                        finished_at=finished_at,
                        input_variables_snapshot=input_snapshot,
                        tool_result=tool_result,
                        validator_result=validator_result,
                        chosen_transition=None,
                        error=None,
                    )
                    ctx.state.history.append(record)
                    if ctx.definition.serialize_enabled:
                        self.storage.save_step_record(ctx.state, record)
                    return
                status = "fail"
                if not message:
                    message = "maximum retries exceeded"

            if status == "fail":
                error = f"validation failed: {message}" if message else "validation failed"
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
                ctx.state.history.append(record)
                if ctx.definition.serialize_enabled:
                    self.storage.save_step_record(ctx.state, record)
                ctx.state.failed = True
                return

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
