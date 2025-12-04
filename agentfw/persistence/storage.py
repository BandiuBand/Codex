from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

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
        raise NotImplementedError()

    def load_state(self, run_id: str) -> AgentState:
        """Load an agent state from the filesystem by run id."""
        raise NotImplementedError()

    def save_step_record(self, state: AgentState, record: StepExecutionRecord) -> None:
        """Persist a step record to the filesystem."""
        raise NotImplementedError()
