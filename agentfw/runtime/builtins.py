from __future__ import annotations

import json
import subprocess
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict

from agentfw.core.agent import VarDecl
from agentfw.llm.base import DummyLLMClient
from agentfw.llm.json_utils import extract_json_from_text


BuiltinFunc = Callable[["ExecutionContext"], Dict[str, Any]]

BUILTIN_PORTS: Dict[str, Dict[str, list[VarDecl]]] = {
    "std.llm_json": {
        "inputs": [
            VarDecl(name="prompt", type="string", required=True),
            VarDecl(name="options", type="object", required=False),
        ],
        "outputs": [
            VarDecl(name="output_text", type="string"),
            VarDecl(name="parsed_json", type="object"),
            VarDecl(name="json_error", type="string"),
        ],
    },
    "std.python": {
        "inputs": [
            VarDecl(name="code", type="string", required=True),
            VarDecl(name="vars", type="object", required=False),
        ],
        "outputs": [
            VarDecl(name="patch", type="object"),
            VarDecl(name="stdout", type="string"),
            VarDecl(name="error", type="string"),
        ],
    },
    "std.shell": {
        "inputs": [
            VarDecl(name="command", type="object", required=True),
            VarDecl(name="cwd", type="string", required=False),
            VarDecl(name="timeout", type="int", required=False),
        ],
        "outputs": [
            VarDecl(name="return_code", type="int"),
            VarDecl(name="stdout", type="string"),
            VarDecl(name="stderr", type="string"),
            VarDecl(name="ok", type="bool"),
        ],
    },
    "std.condition": {
        "inputs": [VarDecl(name="expr", type="string", required=True)],
        "outputs": [VarDecl(name="value", type="bool")],
    },
}


@dataclass
class BuiltinAgentRegistry:
    registry: Dict[str, BuiltinFunc] = field(default_factory=dict)

    def register(self, agent_id: str, fn: BuiltinFunc) -> None:
        self.registry[agent_id] = fn

    def has(self, agent_id: str) -> bool:
        return agent_id in self.registry

    def run(self, agent_id: str, ctx: "ExecutionContext") -> Dict[str, Any]:
        if agent_id not in self.registry:
            raise KeyError(f"Unknown builtin agent '{agent_id}'")
        return self.registry[agent_id](ctx)


def _builtin_llm_json(ctx: "ExecutionContext") -> Dict[str, Any]:
    prompt = str(ctx.get("$in.prompt", ""))
    options = ctx.get("$in.options", {})
    client = DummyLLMClient()
    output_text = client.generate(prompt, **(options if isinstance(options, dict) else {}))
    parsed, error = extract_json_from_text(output_text)
    return {
        "$out.output_text": output_text,
        "$out.parsed_json": parsed,
        "$out.json_error": error,
    }


def _builtin_python(ctx: "ExecutionContext") -> Dict[str, Any]:
    code = str(ctx.get("$in.code", ""))
    vars_payload = ctx.get("$in.vars", {})
    scope: Dict[str, Any] = {}
    if isinstance(vars_payload, dict):
        scope.update(vars_payload)
    stdout_lines: list[str] = []

    def capture_print(*args: Any, **kwargs: Any) -> None:
        text = " ".join(map(str, args))
        stdout_lines.append(text)

    scope["print"] = capture_print

    try:
        compiled = compile(code, "<agent_code>", "exec")
        exec(compiled, scope, scope)  # noqa: S102
    except Exception as exc:  # noqa: BLE001
        return {
            "$out.patch": {},
            "$out.stdout": "\n".join(stdout_lines),
            "$out.error": str(exc),
        }

    patch = scope.get("patch", {})
    return {
        "$out.patch": patch if isinstance(patch, dict) else {},
        "$out.stdout": "\n".join(stdout_lines),
        "$out.error": None,
    }


def _builtin_shell(ctx: "ExecutionContext") -> Dict[str, Any]:
    command = ctx.get("$in.command")
    cwd = ctx.get("$in.cwd")
    timeout = ctx.get("$in.timeout")
    if isinstance(command, list):
        cmd = [str(part) for part in command]
    else:
        cmd = str(command).split()

    try:
        completed = subprocess.run(  # noqa: PLW1510
            cmd,
            cwd=str(Path(cwd)) if cwd else None,
            capture_output=True,
            text=True,
            timeout=int(timeout) if timeout is not None else None,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "$out.return_code": -1,
            "$out.stdout": "",
            "$out.stderr": str(exc),
            "$out.ok": False,
        }

    return {
        "$out.return_code": completed.returncode,
        "$out.stdout": completed.stdout,
        "$out.stderr": completed.stderr,
        "$out.ok": completed.returncode == 0,
    }


def _builtin_condition(ctx: "ExecutionContext") -> Dict[str, Any]:
    value = bool(ctx.get("$in.expr"))
    return {"$out.value": value}


def build_default_registry() -> BuiltinAgentRegistry:
    registry = BuiltinAgentRegistry()
    registry.register("std.llm_json", _builtin_llm_json)
    registry.register("std.python", _builtin_python)
    registry.register("std.shell", _builtin_shell)
    registry.register("std.condition", _builtin_condition)
    return registry


__all__ = ["BuiltinAgentRegistry", "build_default_registry", "BUILTIN_PORTS"]
