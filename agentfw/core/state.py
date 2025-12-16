from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from agentfw.core.models import AgentDefinition

if False:  # pragma: no cover
    from agentfw.runtime.engine import ExecutionEngine


@dataclass
class StepExecutionRecord:
    """Captures execution metadata for a single step."""

    step_id: str
    started_at: float
    finished_at: float
    input_variables_snapshot: Dict[str, object] = field(default_factory=dict)
    tool_result: Dict[str, object] | None = None
    validator_result: Dict[str, object] | None = None
    chosen_transition: Optional[str] = None
    error: Optional[str] = None


@dataclass
class AgentState:
    """Represents the mutable execution state of an agent run."""

    run_id: str
    agent_name: str
    current_step_id: Optional[str] = None
    finished: bool = False
    failed: bool = False
    variables: Dict[str, object] = field(default_factory=dict)
    history: List[StepExecutionRecord] = field(default_factory=list)
    retry_counts: Dict[str, int] = field(default_factory=dict)

    def get_variable(self, name: str, default: object | None = None) -> object:
        """Retrieve a variable value from the agent state."""
        raise NotImplementedError()

    def set_variable(self, name: str, value: object) -> None:
        """Set a variable value in the agent state."""
        raise NotImplementedError()

    def add_history_record(self, record: StepExecutionRecord) -> None:
        """Append a step execution record to the history."""
        raise NotImplementedError()


@dataclass
class ExecutionContext:
    """Aggregates definition, state, and engine during step execution."""

    definition: AgentDefinition
    state: AgentState
    engine: "ExecutionEngine"

    def get_var(self, name: str, default: object | None = None) -> object:
        """Get a variable from the agent state."""
        return self.state.variables.get(name, default)

    def set_var(self, name: str, value: object) -> None:
        """Set a variable in the agent state."""
        self.state.variables[name] = value

    def resolve_template(self, template: str) -> str:
        """Resolve placeholders in the template using current variables."""
        _PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")

        vars_ = self.state.variables

        def repl(m: re.Match) -> str:
            key = m.group(1)
            if key in vars_:
                return str(vars_.get(key, ""))
            return m.group(0)

        return _PLACEHOLDER.sub(repl, template)
