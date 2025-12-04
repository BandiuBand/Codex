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


class EchoTool(BaseTool):
    """Simple tool that echoes back rendered text."""

    def execute(self, ctx: ExecutionContext, params: dict) -> dict:
        """
        Simple test tool that returns a formatted text based on the current variables.
        Expected params:
          - "text": template string with {var_name} placeholders.
        Returns:
          - {"output_text": str}
        """

        template = params.get("text", "")
        rendered = ctx.resolve_template(template)
        return {"output_text": rendered}


class MathAddTool(BaseTool):
    """Test tool that adds two numeric variables from the agent state."""

    def execute(self, ctx: ExecutionContext, params: dict) -> dict:
        """
        Test tool that adds two numeric variables from the agent state.
        Expected params:
          - "a_var": name of the first variable
          - "b_var": name of the second variable
        Returns:
          - {"result": number}
        """

        a_name = params.get("a_var")
        b_name = params.get("b_var")
        a_value = ctx.get_var(a_name)
        b_value = ctx.get_var(b_name)
        result = (a_value or 0) + (b_value or 0)
        return {"result": result}
