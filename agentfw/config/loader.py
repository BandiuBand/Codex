from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import yaml

from agentfw.core.models import (
    AgentDefinition,
    ConditionDefinition,
    StepDefinition,
    TransitionDefinition,
)


class AgentConfigLoader:
    """Loads agent definitions from YAML configuration files."""

    def __init__(self, config_dirs: List[str]) -> None:
        self.config_dirs = config_dirs

    def load_all(self) -> List[AgentDefinition]:
        """Scan all config_dirs for YAML files and parse them."""

        definitions: List[AgentDefinition] = []
        for config_dir in self.config_dirs:
            dir_path = Path(config_dir)
            if not dir_path.exists() or not dir_path.is_dir():
                continue

            for pattern in ("*.yaml", "*.yml"):
                for file_path in dir_path.rglob(pattern):
                    definitions.append(self.load_file(file_path))

        return definitions

    def load_file(self, path: Path) -> AgentDefinition:
        """Load a single YAML file and convert it into an AgentDefinition."""

        data = yaml.safe_load(path.read_text())
        if not isinstance(data, dict):
            raise ValueError(f"Configuration in {path} must be a mapping")

        agent_id = str(data.get("id") or data.get("name", "")).strip()
        if not agent_id:
            raise ValueError(f"Agent name is required in {path}")

        display_name_raw = data.get("name") if data.get("id") else data.get("display_name")
        display_name = str(display_name_raw).strip() if display_name_raw else None

        steps_section = data.get("steps", {}) or {}
        if not isinstance(steps_section, dict):
            raise ValueError(f"'steps' must be a mapping in {path}")

        steps: Dict[str, StepDefinition] = {}
        for step_id, step_data in steps_section.items():
            step_def = self._parse_step(step_id, step_data)
            steps[step_id] = step_def

        entry_step_id = str(data.get("entry_step_id", "")).strip()
        if not entry_step_id:
            raise ValueError(f"entry_step_id is required for agent '{agent_id}'")

        if entry_step_id not in steps:
            raise ValueError(
                f"Entry step '{entry_step_id}' is not defined in steps for agent '{agent_id}'"
            )

        end_step_ids = set(map(str, data.get("end_step_ids", []) or []))
        unknown_end_steps = [step for step in end_step_ids if step not in steps]
        if unknown_end_steps:
            unknown = "', '".join(unknown_end_steps)
            raise ValueError(f"End step '{unknown}' is not defined in steps")

        self._validate_transitions(steps, agent_id)

        serialize_cfg = data.get("serialize", {}) or {}
        if not isinstance(serialize_cfg, dict):
            raise ValueError(f"'serialize' must be a mapping in {path}")

        definition = AgentDefinition(
            name=agent_id,
            display_name=display_name,
            description=data.get("description"),
            input_schema=data.get("input_schema"),
            output_schema=data.get("output_schema"),
            steps=steps,
            entry_step_id=entry_step_id,
            end_step_ids=end_step_ids,
            serialize_enabled=bool(serialize_cfg.get("enabled", False)),
            serialize_base_dir=serialize_cfg.get("base_dir"),
            serialize_per_step=bool(serialize_cfg.get("per_step", False)),
        )

        return definition

    def _parse_step(self, step_id: str, data: Dict[str, object]) -> StepDefinition:
        if not step_id:
            raise ValueError("Step id cannot be empty")

        if not isinstance(data, dict):
            raise ValueError(f"Step '{step_id}' must be a mapping")

        transitions_data = data.get("transitions", []) or []
        transitions = [self._parse_transition(t) for t in transitions_data]

        return StepDefinition(
            id=step_id,
            name=data.get("name"),
            kind=str(data.get("kind", "")),
            tool_name=data.get("tool_name"),
            tool_params=data.get("tool_params", {}) or {},
            save_mapping=data.get("save_mapping", {}) or {},
            validator_agent_name=data.get("validator_agent_name"),
            validator_params=data.get("validator_params", {}) or {},
            validator_policy=data.get("validator_policy", {}) or {},
            transitions=transitions,
        )

    def _parse_transition(self, data: Dict[str, object]) -> TransitionDefinition:
        if not isinstance(data, dict):
            raise ValueError("Transition must be a mapping")

        target_step_id = data.get("target_step_id")
        if target_step_id is None:
            raise ValueError("Transition missing target_step_id")

        condition_data = data.get("condition")
        if condition_data is None:
            raise ValueError(
                f"Transition to '{target_step_id}' must define a condition"
            )

        condition = self._parse_condition(condition_data)
        return TransitionDefinition(target_step_id=str(target_step_id), condition=condition)

    def _parse_condition(self, data: Dict[str, object]) -> ConditionDefinition:
        if not isinstance(data, dict):
            raise ValueError("Condition must be a mapping")

        cond_type = str(data.get("type", "")).strip()
        if not cond_type:
            raise ValueError("Condition type is required")

        known_keys = {"type", "value_from", "value", "right_var", "expression"}
        extra = {k: v for k, v in data.items() if k not in known_keys}

        return ConditionDefinition(
            type=cond_type,
            value_from=data.get("value_from"),
            value=data.get("value"),
            right_var=data.get("right_var"),
            expression=data.get("expression"),
            extra=extra,
        )

    def _validate_transitions(self, steps: Dict[str, StepDefinition], agent_name: str) -> None:
        for step_id, step in steps.items():
            for transition in step.transitions:
                target_id = transition.target_step_id
                if target_id not in steps:
                    raise ValueError(
                        f"Unknown step '{target_id}' referenced in transition of step '{step_id}'"
                    )
