from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from agentfw.core.agent_spec import AgentSpec, agent_spec_from_dict, agent_spec_to_dict


def load_agent_spec(path: Path) -> AgentSpec:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return agent_spec_from_dict(data)


def save_agent_spec(path: Path, spec: AgentSpec) -> None:
    payload: Dict[str, Any] = agent_spec_to_dict(spec)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        yaml.safe_dump(payload, fp, sort_keys=False, allow_unicode=True)


__all__ = ["load_agent_spec", "save_agent_spec", "agent_spec_from_dict", "agent_spec_to_dict"]
