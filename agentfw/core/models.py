from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class ConditionDefinition:
    """Container for a transition condition described in configuration."""

    type: str
    value_from: Optional[str] = None
    value: object | None = None
    expression: Optional[str] = None
    extra: Dict[str, object] = field(default_factory=dict)


@dataclass
class TransitionDefinition:
    """Describes a transition between steps with an associated condition."""

    target_step_id: str
    condition: ConditionDefinition

    def is_default(self) -> bool:
        """Return True when the transition condition represents an always-true case."""
        raise NotImplementedError()


@dataclass
class StepDefinition:
    """Represents a single step within an agent graph."""

    id: str
    name: Optional[str] = None
    kind: str = ""
    tool_name: Optional[str] = None
    tool_params: Dict[str, object] = field(default_factory=dict)
    save_mapping: Dict[str, str] = field(default_factory=dict)
    validator_agent_name: Optional[str] = None
    validator_params: Dict[str, object] = field(default_factory=dict)
    validator_policy: Dict[str, str] = field(default_factory=dict)
    transitions: List[TransitionDefinition] = field(default_factory=list)

    def get_transitions(self) -> List[TransitionDefinition]:
        """Return the list of possible transitions from this step."""
        raise NotImplementedError()


@dataclass
class AgentDefinition:
    """Defines an agent loaded from configuration files."""

    name: str
    description: Optional[str] = None
    input_schema: Dict[str, object] | None = None
    output_schema: Dict[str, object] | None = None
    steps: Dict[str, StepDefinition] = field(default_factory=dict)
    entry_step_id: str = ""
    end_step_ids: Set[str] = field(default_factory=set)
    serialize_enabled: bool = False
    serialize_base_dir: Optional[str] = None
    serialize_per_step: bool = False

    def get_step(self, step_id: str) -> StepDefinition:
        """Return a step definition by id or raise if it is missing."""
        try:
            return self.steps[step_id]
        except KeyError:
            raise KeyError(f"Step '{step_id}' not found in agent '{self.name}'")
