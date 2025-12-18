from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional


@dataclass
class PythonTool:
    allowed_outputs: Optional[Iterable[str]] = None

    def run(self, variables: Dict[str, Any]) -> Dict[str, Any]:
        code = str(variables.get("code", ""))
        sandbox: Dict[str, Any] = {}
        sandbox.update(variables)
        stdout_lines: list[str] = []

        def capture_print(*args: Any, **kwargs: Any) -> None:  # noqa: ARG001
            stdout_lines.append(" ".join(map(str, args)))

        sandbox["print"] = capture_print

        try:
            compiled = compile(code, "<python_tool>", "exec")
            exec(compiled, sandbox, sandbox)  # noqa: S102
        except Exception as exc:  # noqa: BLE001
            sandbox["error"] = str(exc)

        if stdout_lines:
            sandbox["stdout"] = "\n".join(stdout_lines)

        if self.allowed_outputs is None:
            return sandbox
        allowed = set(self.allowed_outputs)
        return {k: v for k, v in sandbox.items() if k in allowed}


__all__ = ["PythonTool"]
