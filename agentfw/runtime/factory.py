from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

from agentfw.runtime.engine import AgentRepository, ExecutionEngine


def find_agents_dir() -> Path:
    env_dir = os.environ.get("AGENTFW_AGENTS_DIR")
    if env_dir:
        return Path(env_dir)

    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        candidate = parent / "agents"
        if candidate.exists() and candidate.is_dir():
            return candidate

    project_root = Path(__file__).resolve().parents[2]
    return project_root / "agents"


def build_default_engine() -> Tuple[ExecutionEngine, AgentRepository]:
    agents_dir = find_agents_dir()
    repository = AgentRepository(agents_dir)
    engine = ExecutionEngine(repository=repository)
    return engine, repository


__all__ = ["build_default_engine", "find_agents_dir"]
