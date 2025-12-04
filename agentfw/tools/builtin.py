from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

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

        agent_name = params.get("agent_name")
        if not agent_name:
            raise ValueError("AgentCallTool requires 'agent_name' in params")

        input_mapping = params.get("input_mapping") or {}
        output_mapping = params.get("output_mapping") or []

        if not isinstance(input_mapping, dict):
            raise ValueError("'input_mapping' must be a dict if provided")

        child_input: Dict[str, Any] = {}
        for child_key, parent_var in input_mapping.items():
            child_input[child_key] = ctx.get_var(str(parent_var))

        child_state = self.engine.run_to_completion(agent_name=str(agent_name), input_json=child_input)

        result: Dict[str, Any] = {
            "__child_run_id": child_state.run_id,
            "__child_agent_name": child_state.agent_name,
            "__child_finished": child_state.finished,
            "__child_failed": child_state.failed,
        }

        if isinstance(output_mapping, dict):
            for parent_var, child_var in output_mapping.items():
                result[parent_var] = child_state.variables.get(str(child_var))
        elif isinstance(output_mapping, list):
            for var_name in output_mapping:
                key = str(var_name)
                result[key] = child_state.variables.get(key)

        return result


class ShellTool(BaseTool):
    """Tool skeleton for executing shell commands."""

    def execute(self, ctx: ExecutionContext, params: Dict[str, object]) -> Dict[str, object]:
        """Run a shell command using the provided parameters."""

        command: Union[str, List[str], None] = params.get("command")
        if command is None:
            raise ValueError("ShellTool requires a 'command' parameter")

        if isinstance(command, list):
            command_arg: Union[str, List[str]] = [str(part) for part in command]
        elif isinstance(command, str):
            command_arg = command
        else:
            raise ValueError("ShellTool 'command' must be a string or list")

        allow_failure = bool(params.get("allow_failure", True))
        cwd = params.get("cwd")
        timeout = params.get("timeout")
        env = params.get("env")

        result = subprocess.run(
            command_arg,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
            env=env,
        )

        output = {
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "ok": result.returncode == 0,
        }

        if not allow_failure and result.returncode != 0:
            raise RuntimeError(f"Command failed with return code {result.returncode}")

        return output


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


@dataclass
class AcceptValidatorTool(BaseTool):
    """Simple tool that unconditionally approves validation."""

    default_message: str = "Validation accepted"

    def execute(self, ctx: ExecutionContext, params: dict) -> dict:
        message = str(params.get("message", self.default_message))
        patch = params.get("patch") or {}

        if patch is not None and not isinstance(patch, dict):
            raise ValueError("AcceptValidatorTool 'patch' param must be a mapping if provided")

        validation_result: Dict[str, object] = {
            "status": "accept",
            "message": message,
        }

        if isinstance(patch, dict) and patch:
            validation_result["patch"] = patch

        return {"validation": validation_result}


class FlakyTool(BaseTool):
    """Tool that increments a counter stored in the execution context."""

    def execute(self, ctx: ExecutionContext, params: Dict[str, object]) -> Dict[str, object]:
        counter_var = params.get("counter_var")
        if not counter_var:
            raise ValueError("FlakyTool requires 'counter_var' in params")

        counter_name = str(counter_var)
        current_value = ctx.get_var(counter_name, 0)
        if not isinstance(current_value, int):
            raise ValueError("FlakyTool counter must be an integer")

        new_value = current_value + 1
        ctx.set_var(counter_name, new_value)

        return {"counter": new_value}
