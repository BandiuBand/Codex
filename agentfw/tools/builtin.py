from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from agentfw.core.state import ExecutionContext
from agentfw.runtime.engine import ExecutionEngine
from agentfw.tools.base import BaseTool


@dataclass
class LLMTool(BaseTool):
    """Abstract tool representing a language model backend call."""

    backend_name: Optional[str] = None

    def execute(self, ctx: ExecutionContext, params: Dict[str, object]) -> Dict[str, object]:
        """Invoke the language model backend with provided parameters."""
        raise NotImplementedError()


@dataclass
class AgentCallTool(BaseTool):
    """Tool for invoking another agent via the execution engine."""

    engine: ExecutionEngine

    def execute(self, ctx: ExecutionContext, params: Dict[str, object]) -> Dict[str, object]:
        """Delegate execution to another agent using the engine."""
        raise NotImplementedError()


class ShellTool(BaseTool):
    """Tool skeleton for executing shell commands."""

    def execute(self, ctx: ExecutionContext, params: Dict[str, object]) -> Dict[str, object]:
        """Run a shell command using the provided parameters."""
        raise NotImplementedError()
