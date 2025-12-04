from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from agentfw.core.state import ExecutionContext
from agentfw.runtime.engine import ExecutionEngine
from agentfw.tools.base import BaseTool
from agentfw.llm.base import LLMClient


@dataclass
class LLMTool(BaseTool):
    """
    Tool that calls an LLMClient to generate text based on a prompt template.

    The behavior is controlled entirely by 'params' from the step definition.
    """

    client: LLMClient

    def execute(self, ctx: ExecutionContext, params: Dict[str, Any]) -> Dict[str, Any]:
        has_prompt = "prompt" in params
        has_prompt_var = "prompt_var" in params

        if not (has_prompt or has_prompt_var):
            raise ValueError("LLMTool requires either 'prompt' or 'prompt_var'")

        prompt: Optional[str]
        if has_prompt:
            template = str(params.get("prompt", ""))
            prompt = ctx.resolve_template(template)
        else:
            var_name = str(params.get("prompt_var"))
            prompt = str(ctx.get_var(var_name, ""))

        options = params.get("options", {}) or {}
        if not isinstance(options, dict):
            raise ValueError("LLMTool 'options' must be a mapping if provided")

        output_text = self.client.generate(prompt, **options)

        return {
            "prompt": prompt,
            "output_text": output_text,
        }


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
