from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import json
from pathlib import Path

from agentfw.core.state import AgentState, StepExecutionRecord


class RunStorage(ABC):
    """Abstract interface for persisting agent run states and history."""

    @abstractmethod
    def save_state(self, state: AgentState) -> None:
        """Persist the current agent state."""
        raise NotImplementedError()

    @abstractmethod
    def load_state(self, run_id: str) -> AgentState:
        """Load a previously saved agent state by run id."""
        raise NotImplementedError()

    @abstractmethod
    def save_step_record(self, state: AgentState, record: StepExecutionRecord) -> None:
        """Persist a step execution record associated with an agent state."""
        raise NotImplementedError()


@dataclass
class FileRunStorage(RunStorage):
    """File-based implementation placeholder for run storage."""

    base_dir: str

    def save_state(self, state: AgentState) -> None:
        """Persist the current agent state to the filesystem."""
        run_dir = Path(self.base_dir) / state.run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "run_id": state.run_id,
            "agent_name": state.agent_name,
            "current_step_id": state.current_step_id,
            "finished": state.finished,
            "failed": state.failed,
            "variables": state.variables,
        }

        with (run_dir / "state.json").open("w", encoding="utf-8") as f:
            json.dump(data, f)

    def load_state(self, run_id: str) -> AgentState:
        """Load an agent state from the filesystem by run id."""
        raise NotImplementedError()

    def save_step_record(self, state: AgentState, record: StepExecutionRecord) -> None:
        """Persist a step record to the filesystem."""
        run_dir = Path(self.base_dir) / state.run_id / "steps"
        run_dir.mkdir(parents=True, exist_ok=True)

        index = len(state.history)
        filename = f"{index:03d}_{record.step_id}.json"

        data = {
            "step_id": record.step_id,
            "started_at": record.started_at,
            "finished_at": record.finished_at,
            "input_variables_snapshot": record.input_variables_snapshot,
            "tool_result": record.tool_result,
            "validator_result": record.validator_result,
            "chosen_transition": record.chosen_transition,
            "error": record.error,
        }

        with (run_dir / filename).open("w", encoding="utf-8") as f:
            json.dump(data, f)
