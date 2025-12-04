from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from agentfw.config.loader import AgentConfigLoader
from agentfw.core.models import AgentDefinition
from agentfw.tools.base import BaseTool


@dataclass
class AgentRegistry:
    """Registry that stores agent definitions by name."""

    agents: Dict[str, AgentDefinition] = field(default_factory=dict)
    config_dirs: List[str] = field(default_factory=list)
    config_loader: Optional[AgentConfigLoader] = None

    def load_all(self) -> None:
        """Load agent definitions from YAML configuration files."""
        if not self.config_dirs:
            return

        if self.config_loader is None:
            self.config_loader = AgentConfigLoader(self.config_dirs)

        definitions = self.config_loader.load_all()
        for definition in definitions:
            self.register(definition)

    def reload(self) -> None:
        """Clear registry and reload all agent definitions."""
        self.agents.clear()
        self.load_all()

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
