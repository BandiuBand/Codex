from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass
class ShellTool:
    allow_failure: bool = False
    timeout: Optional[float] = None
    cwd: Optional[Path] = None

    def run(self, variables: Dict[str, Any]) -> Dict[str, Any]:
        command = variables.get("command")
        if command is None:
            raise ValueError("ShellTool requires 'command'")
        cwd = variables.get("cwd", self.cwd)
        timeout = variables.get("timeout", self.timeout)
        allow_failure = bool(variables.get("allow_failure", self.allow_failure))
        if variables.get("env"):
            raise ValueError("env override is not allowed")
        cmd: Union[str, List[str]]
        if isinstance(command, list):
            cmd = [str(part) for part in command]
        else:
            cmd = str(command)

        try:
            completed = subprocess.run(  # noqa: S603, PLW1510
                cmd,
                cwd=str(cwd) if cwd else None,
                timeout=float(timeout) if timeout is not None else None,
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as exc:  # noqa: BLE001
            return {"return_code": -1, "stdout": "", "stderr": str(exc), "ok": False}

        result = {
            "return_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "ok": completed.returncode == 0,
        }
        if completed.returncode != 0 and not allow_failure:
            raise RuntimeError(f"Command failed with return code {completed.returncode}")
        return result


__all__ = ["ShellTool"]
