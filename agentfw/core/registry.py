from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from agentfw.core.models import AgentDefinition
from agentfw.tools.base import BaseTool


@dataclass
class AgentRegistry:
    """Registry that stores agent definitions by name."""

    agents: Dict[str, AgentDefinition] = field(default_factory=dict)
    config_dirs: List[str] = field(default_factory=list)

    def load_all(self) -> None:
        """Placeholder for loading all agent configurations."""
        raise NotImplementedError()

    def reload(self) -> None:
        """Placeholder for reloading agent configurations."""
        raise NotImplementedError()

    def register(self, definition: AgentDefinition) -> None:
        """Register an agent definition in the registry."""
        self.agents[definition.name] = definition

    def get(self, name: str) -> AgentDefinition:
        """Retrieve an agent definition by name or raise if missing."""
        try:
            return self.agents[name]
        except KeyError:
            raise KeyError(f"Agent '{name}' is not registered")


@dataclass
class ToolRegistry:
    """Registry that maps tool names to tool instances."""

    tools: Dict[str, BaseTool] = field(default_factory=dict)

    def register(self, name: str, tool: BaseTool) -> None:
        """Register a tool instance under the given name."""
        self.tools[name] = tool

    def get(self, name: str) -> BaseTool:
        """Retrieve a tool by name or raise if not found."""
        try:
            return self.tools[name]
        except KeyError:
            raise KeyError(f"Tool '{name}' is not registered")
