from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List

import yaml

from agentfw.config.loader import AgentConfigLoader
from agentfw.core.models import AgentDefinition, ConditionDefinition, StepDefinition, TransitionDefinition
from agentfw.tools import builtin as builtin_tools


DEFAULT_CONDITIONS = [
    "always",
    "equals",
    "not_equals",
    "greater_than",
    "less_than",
    "contains",
    "expression",
]


def _find_agents_dir() -> Path:
    env_dir = os.environ.get("AGENTFW_AGENTS_DIR")
    if env_dir:
        return Path(env_dir)

    project_root = Path(__file__).resolve().parents[2]
    default = project_root / "agents"
    if default.exists() or project_root.exists():
        return default
    return Path.cwd() / "agents"


def _condition_to_dict(condition: ConditionDefinition) -> Dict[str, object]:
    data: Dict[str, object] = {"type": condition.type}
    if condition.value_from is not None:
        data["value_from"] = condition.value_from
    if condition.value is not None:
        data["value"] = condition.value
    if condition.expression is not None:
        data["expression"] = condition.expression
    for key, value in (condition.extra or {}).items():
        if key not in data:
            data[key] = value
    return data


def _transition_to_dict(transition: TransitionDefinition) -> Dict[str, object]:
    return {
        "target_step_id": transition.target_step_id,
        "condition": _condition_to_dict(transition.condition),
    }


def definition_to_dict(definition: AgentDefinition) -> Dict[str, object]:
    steps: Dict[str, object] = {}
    for step_id, step in definition.steps.items():
        steps[step_id] = {
            "name": step.name,
            "kind": step.kind,
            "tool_name": step.tool_name,
            "tool_params": step.tool_params,
            "save_mapping": step.save_mapping,
            "validator_agent_name": step.validator_agent_name,
            "validator_params": step.validator_params,
            "validator_policy": step.validator_policy,
            "transitions": [_transition_to_dict(t) for t in step.transitions],
        }

    serialize_cfg = {
        "enabled": bool(definition.serialize_enabled),
        "base_dir": definition.serialize_base_dir,
        "per_step": bool(definition.serialize_per_step),
    }

    return {
        "name": definition.name,
        "description": definition.description,
        "input_schema": definition.input_schema,
        "output_schema": definition.output_schema,
        "steps": steps,
        "entry_step_id": definition.entry_step_id,
        "end_step_ids": sorted(definition.end_step_ids),
        "serialize": serialize_cfg,
    }


def _parse_condition(loader: AgentConfigLoader, data: Dict[str, object]) -> ConditionDefinition:
    return loader._parse_condition(data)  # pylint: disable=protected-access


def _parse_transition(loader: AgentConfigLoader, data: Dict[str, object]) -> TransitionDefinition:
    return loader._parse_transition(data)  # pylint: disable=protected-access


def _parse_step(loader: AgentConfigLoader, step_id: str, data: Dict[str, object]) -> StepDefinition:
    return loader._parse_step(step_id, data)  # pylint: disable=protected-access


def definition_from_dict(data: Dict[str, object]) -> AgentDefinition:
    loader = AgentConfigLoader([])

    name = str(data.get("name", "")).strip()
    if not name:
        raise ValueError("Agent name is required")

    steps_section = data.get("steps", {}) or {}
    if not isinstance(steps_section, dict):
        raise ValueError("'steps' must be a mapping")

    steps: Dict[str, StepDefinition] = {}
    for step_id, step_data in steps_section.items():
        steps[str(step_id)] = _parse_step(loader, str(step_id), step_data or {})

    entry_step_id = str(data.get("entry_step_id", "")).strip()
    if not entry_step_id:
        raise ValueError("entry_step_id is required")
    if entry_step_id not in steps:
        raise ValueError(f"Entry step '{entry_step_id}' is not defined in steps for agent '{name}'")

    end_step_ids = set(map(str, data.get("end_step_ids", []) or []))
    unknown_end_steps = [step for step in end_step_ids if step not in steps]
    if unknown_end_steps:
        unknown = "', '".join(unknown_end_steps)
        raise ValueError(f"End step '{unknown}' is not defined in steps")

    loader._validate_transitions(steps, name)  # pylint: disable=protected-access

    serialize_cfg = data.get("serialize", {}) or {}
    if not isinstance(serialize_cfg, dict):
        raise ValueError("'serialize' must be a mapping")

    return AgentDefinition(
        name=name,
        description=data.get("description"),
        input_schema=data.get("input_schema"),
        output_schema=data.get("output_schema"),
        steps=steps,
        entry_step_id=entry_step_id,
        end_step_ids=end_step_ids,
        serialize_enabled=bool(serialize_cfg.get("enabled", False)),
        serialize_base_dir=serialize_cfg.get("base_dir"),
        serialize_per_step=bool(serialize_cfg.get("per_step", False)),
    )


def _load_yaml_definition(path: Path) -> AgentDefinition:
    loader = AgentConfigLoader([str(path.parent)])
    return loader.load_file(path)


def _write_yaml_definition(path: Path, definition: AgentDefinition) -> None:
    payload = definition_to_dict(definition)
    with path.open("w", encoding="utf-8") as fp:
        yaml.safe_dump(payload, fp, sort_keys=False, allow_unicode=True)


def _list_available_tools() -> List[str]:
    tools = []
    for name in dir(builtin_tools):
        if name.endswith("Tool") and name[0].isupper():
            tools.append(name)
    return sorted(tools)


class AgentWebHandler(SimpleHTTPRequestHandler):
    server_version = "AgentWeb/0.1"

    def __init__(self, *args, **kwargs):
        self.agents_dir = _find_agents_dir()
        self.static_dir = Path(__file__).parent / "static"
        self.tools = _list_available_tools()
        super().__init__(*args, directory=str(self.static_dir), **kwargs)

    def end_headers(self) -> None:  # type: ignore[override]
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api/tools"):
            return self._handle_tools()
        if self.path.startswith("/api/agents"):
            return self._handle_agents_get()
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if self.path.startswith("/api/agents/validate"):
            return self._handle_validate()
        if self.path.startswith("/api/agents/"):
            return self._handle_agent_save()
        self.send_error(HTTPStatus.NOT_FOUND, "Unknown API endpoint")

    def do_PUT(self) -> None:  # noqa: N802
        return self.do_POST()

    def _read_json_body(self) -> Dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON payload: {exc}") from exc

    def _send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_tools(self) -> None:
        payload = {"tools": self.tools, "conditions": DEFAULT_CONDITIONS}
        self._send_json(payload)

    def _handle_agents_get(self) -> None:
        base = "/api/agents/"
        if self.path == "/api/agents" or self.path == base:
            names = []
            if self.agents_dir.exists():
                for file in self.agents_dir.glob("*.yml"):
                    names.append(file.stem)
                for file in self.agents_dir.glob("*.yaml"):
                    names.append(file.stem)
            names = sorted(set(names))
            return self._send_json({"agents": names})

        agent_name = self.path[len(base) :]
        if not agent_name:
            return self.send_error(HTTPStatus.BAD_REQUEST, "Agent name required")

        path = self._agent_path(agent_name)
        if not path.exists():
            return self.send_error(HTTPStatus.NOT_FOUND, "Agent not found")

        definition = _load_yaml_definition(path)
        return self._send_json(definition_to_dict(definition))

    def _handle_agent_save(self) -> None:
        agent_name = self.path.split("/api/agents/")[-1]
        if not agent_name:
            return self.send_error(HTTPStatus.BAD_REQUEST, "Agent name required")

        try:
            payload = self._read_json_body()
            payload["name"] = agent_name
            definition = definition_from_dict(payload)
        except Exception as exc:  # pylint: disable=broad-except
            return self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

        self.agents_dir.mkdir(parents=True, exist_ok=True)
        target_path = self._agent_path(agent_name)
        _write_yaml_definition(target_path, definition)
        return self._send_json({"ok": True, "path": str(target_path)})

    def _handle_validate(self) -> None:
        try:
            payload = self._read_json_body()
            definition = definition_from_dict(payload)
            _ = definition  # explicit use
        except Exception as exc:  # pylint: disable=broad-except
            return self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

        return self._send_json({"ok": True})

    def _agent_path(self, agent_name: str) -> Path:
        safe_name = agent_name.replace("/", "_").replace("\\", "_")
        return self.agents_dir / f"{safe_name}.yaml"


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    handler = AgentWebHandler
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Serving web editor on http://{host}:{port}")
    print(f"Agents directory: {_find_agents_dir()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down...")
        server.server_close()


__all__ = [
    "run_server",
    "definition_from_dict",
    "definition_to_dict",
]
