from __future__ import annotations

import os
import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

from agentfw.config.loader import AgentConfigLoader
from agentfw.core.models import AgentDefinition, ConditionDefinition, StepDefinition, TransitionDefinition
from agentfw.core.state import AgentState
from agentfw.core.registry import AgentRegistry
from agentfw.runtime.engine import ExecutionEngine
from agentfw.runtime.factory import build_default_engine, find_agents_dir
from agentfw.tools import builtin as builtin_tools
from agentfw.tools.base import BaseTool
from agentfw.tools.metadata import TOOL_META


_find_agents_dir = find_agents_dir


DEFAULT_CONDITIONS: List[Dict[str, object]] = [
    {"type": "always", "label_uk": "завжди", "fields": []},
    {
        "type": "equals",
        "label_uk": "змінна дорівнює значенню",
        "fields": [
            {"name": "value_from", "label_uk": "Ім’я змінної"},
            {"name": "value", "label_uk": "Значення"},
        ],
    },
    {
        "type": "not_equals",
        "label_uk": "змінна не дорівнює значенню",
        "fields": [
            {"name": "value_from", "label_uk": "Ім’я змінної"},
            {"name": "value", "label_uk": "Значення"},
        ],
    },
    {
        "type": "greater_than",
        "label_uk": "більше за значення",
        "fields": [
            {"name": "value_from", "label_uk": "Ім’я змінної"},
            {"name": "value", "label_uk": "Значення"},
            {
                "name": "right_var",
                "label_uk": "Ім’я змінної справа (необов’язково)",
            },
        ],
    },
    {
        "type": "less_than",
        "label_uk": "менше за значення",
        "fields": [
            {"name": "value_from", "label_uk": "Ім’я змінної"},
            {"name": "value", "label_uk": "Значення"},
            {
                "name": "right_var",
                "label_uk": "Ім’я змінної справа (необов’язково)",
            },
        ],
    },
    {
        "type": "contains",
        "label_uk": "список/рядок містить значення",
        "fields": [
            {"name": "value_from", "label_uk": "Ім’я змінної"},
            {"name": "value", "label_uk": "Значення"},
        ],
    },
    {
        "type": "expression",
        "label_uk": "вираз на Python",
        "fields": [
            {"name": "expression", "label_uk": "Вираз (наприклад: sum > 10)"},
        ],
    },
]


def _condition_to_dict(condition: ConditionDefinition) -> Dict[str, object]:
    data: Dict[str, object] = {"type": condition.type}
    if condition.value_from is not None:
        data["value_from"] = condition.value_from
    if condition.value is not None:
        data["value"] = condition.value
    if condition.right_var is not None:
        data["right_var"] = condition.right_var
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
        "id": definition.name,
        "name": definition.display_name or definition.name,
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

    agent_id = str(data.get("id") or data.get("name", "")).strip()
    if not agent_id:
        raise ValueError("Agent name is required")

    display_name_raw = data.get("name") if data.get("id") else data.get("display_name")
    display_name = str(display_name_raw).strip() if display_name_raw else None

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
        raise ValueError(
            f"Entry step '{entry_step_id}' is not defined in steps for agent '{agent_id}'"
        )

    end_step_ids = set(map(str, data.get("end_step_ids", []) or []))
    unknown_end_steps = [step for step in end_step_ids if step not in steps]
    if unknown_end_steps:
        unknown = "', '".join(unknown_end_steps)
        raise ValueError(f"End step '{unknown}' is not defined in steps")

    loader._validate_transitions(steps, agent_id)  # pylint: disable=protected-access

    serialize_cfg = data.get("serialize", {}) or {}
    if not isinstance(serialize_cfg, dict):
        raise ValueError("'serialize' must be a mapping")

    return AgentDefinition(
        name=agent_id,
        display_name=display_name,
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


def _camel_to_snake(name: str) -> str:
    result = []
    for char in name:
        if char.isupper() and result:
            result.append("_")
        result.append(char.lower())
    return "".join(result)


def _list_available_tools() -> List[Dict[str, str]]:
    registry = getattr(builtin_tools, "tool_registry", None)
    tools: List[Dict[str, str]] = []

    if isinstance(registry, dict):
        for name, tool in registry.items():
            meta = TOOL_META.get(name, {})
            tools.append(
                {
                    "name": name,
                    "description": (tool.__doc__ or "").strip(),
                    "label_uk": meta.get("label_uk"),
                    "description_uk": meta.get("description_uk"),
                    "category": meta.get("category"),
                    "schema": meta.get("schema"),
                }
            )
    else:
        for attr in dir(builtin_tools):
            obj = getattr(builtin_tools, attr)
            if not isinstance(obj, type):
                continue
            if not issubclass(obj, BaseTool) or obj is BaseTool:
                continue

            tool_name = _camel_to_snake(attr.removesuffix("Tool"))
            meta = TOOL_META.get(tool_name, {})
            tools.append(
                {
                    "name": tool_name,
                    "description": (obj.__doc__ or "").strip(),
                    "label_uk": meta.get("label_uk"),
                    "description_uk": meta.get("description_uk"),
                    "category": meta.get("category"),
                    "schema": meta.get("schema"),
                }
            )

    return sorted(tools, key=lambda t: t["name"])


def _build_runtime() -> Tuple[ExecutionEngine, AgentRegistry]:
    return build_default_engine()


class AgentEditorHandler(SimpleHTTPRequestHandler):
    server_version = "AgentEditor/0.1"

    def __init__(self, *args, **kwargs):
        self.agents_dir = find_agents_dir()
        self.static_dir = Path(__file__).parent / "static"
        self.tools = _list_available_tools()
        super().__init__(*args, directory=str(self.static_dir), **kwargs)

    def end_headers(self) -> None:  # type: ignore[override]
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/tools":
            return self._handle_tools()
        if self.path == "/api/agents_graph":
            return self._handle_agents_graph()
        if self.path.startswith("/api/agents"):
            return self._handle_agent_get()
        if self.path.startswith("/api/"):
            return self._json_error("Unknown API endpoint", status=HTTPStatus.NOT_FOUND)

        if self.path == "/":
            self.path = "/index.html"

        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/agents/validate":
            return self._handle_validate()
        if self.path == "/api/agents/run":
            return self._handle_agent_run()
        if self.path == "/api/run":
            return self._handle_run()
        if self.path.startswith("/api/agents/"):
            return self._handle_agent_save()
        self._json_error("Unknown API endpoint", status=HTTPStatus.NOT_FOUND)

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

    def _json_error(self, message: str, status: HTTPStatus) -> None:
        self._send_json({"ok": False, "error": message}, status=status)

    def _truncate_value(self, value: object, max_length: int = 500, max_items: int = 50) -> object:
        """Recursively trim large strings/collections to keep payloads small."""

        if isinstance(value, str):
            return value if len(value) <= max_length else value[:max_length] + "…"

        if isinstance(value, list):
            trimmed = [self._truncate_value(v, max_length, max_items) for v in value[:max_items]]
            if len(value) > max_items:
                trimmed.append(f"… {len(value) - max_items} more items")
            return trimmed

        if isinstance(value, dict):
            trimmed_dict: Dict[str, object] = {}
            for i, (k, v) in enumerate(value.items()):
                if i >= max_items:
                    trimmed_dict["__truncated__"] = f"… {len(value) - max_items} more entries"
                    break
                trimmed_dict[str(k)] = self._truncate_value(v, max_length, max_items)
            return trimmed_dict

        return value

    def _serialize_history(self, state: AgentState, definition: AgentDefinition) -> List[Dict[str, object]]:
        history: List[Dict[str, object]] = []
        for record in state.history:
            step_def = definition.steps.get(record.step_id)
            history.append(
                {
                    "step_id": record.step_id,
                    "tool_name": step_def.tool_name if step_def else None,
                    "input_variables": self._truncate_value(record.input_variables_snapshot),
                    "tool_result": self._truncate_value(record.tool_result),
                    "validator_result": self._truncate_value(record.validator_result),
                    "chosen_transition": record.chosen_transition,
                    "error": record.error,
                }
            )
        return history

    def _handle_tools(self) -> None:
        payload = {"tools": self.tools, "conditions": DEFAULT_CONDITIONS}
        self._send_json(payload)

    def _handle_agent_get(self) -> None:
        base = "/api/agents/"
        if self.path.rstrip("/") == "/api/agents":
            definitions: Dict[str, Dict[str, str]] = {}
            if self.agents_dir.exists():
                loader = AgentConfigLoader([str(self.agents_dir)])
                files = list(self.agents_dir.glob("*.yml")) + list(
                    self.agents_dir.glob("*.yaml")
                )
                for file in files:
                    try:
                        definition = loader.load_file(file)
                    except Exception:
                        continue
                    definitions[definition.name] = {
                        "id": definition.name,
                        "name": definition.display_name or definition.name,
                    }

            agents_list = sorted(definitions.values(), key=lambda a: a["id"])
            return self._send_json({"agents": agents_list})

        agent_name = self.path[len(base) :]
        if not agent_name:
            return self._json_error("Agent name required", status=HTTPStatus.BAD_REQUEST)

        path = self._agent_path(agent_name)
        if not path.exists():
            return self._json_error("agent not found", status=HTTPStatus.NOT_FOUND)

        try:
            definition = _load_yaml_definition(path)
        except FileNotFoundError:
            return self._json_error("agent not found", status=HTTPStatus.NOT_FOUND)
        except Exception as exc:  # pylint: disable=broad-except
            return self._send_json(
                {"error": f"invalid YAML: {exc}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR
            )

        return self._send_json(definition_to_dict(definition))

    def _handle_agent_save(self) -> None:
        agent_name = self.path.split("/api/agents/")[-1]
        if not agent_name:
            return self._json_error("Agent name required", status=HTTPStatus.BAD_REQUEST)

        try:
            payload = self._read_json_body()
            payload.setdefault("name", payload.get("display_name"))
            payload["id"] = agent_name
            definition = definition_from_dict(payload)
        except ValueError as exc:
            return self._send_json(
                {"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST
            )
        except Exception as exc:  # pylint: disable=broad-except
            return self._send_json(
                {"ok": False, "error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR
            )

        self.agents_dir.mkdir(parents=True, exist_ok=True)
        target_path = self._agent_path(agent_name)
        _write_yaml_definition(target_path, definition)
        return self._send_json({"ok": True})

    def _handle_validate(self) -> None:
        try:
            payload = self._read_json_body()
            definition = definition_from_dict(payload)
            _ = definition  # explicit use
        except ValueError as exc:
            return self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pylint: disable=broad-except
            return self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

        return self._send_json({"ok": True})

    def _handle_run(self) -> None:
        try:
            payload = self._read_json_body()
            agent_name = str(payload.get("agent", "")).strip()
            input_payload = payload.get("input", {}) or {}
            if not agent_name:
                raise ValueError("agent is required")
            if not isinstance(input_payload, dict):
                raise ValueError("input must be an object")
        except Exception as exc:  # pylint: disable=broad-except
            return self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

        try:
            engine, agent_registry = _build_runtime()
            state = engine.run_to_completion(agent_name=agent_name, input_json=input_payload)
            definition = agent_registry.get(agent_name)
        except Exception as exc:  # pylint: disable=broad-except
            return self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

        history = self._serialize_history(state, definition)

        payload = {
            "ok": True,
            "failed": state.failed,
            "final_state": self._truncate_value(state.variables),
            "history": history,
        }

        return self._send_json(payload)

    def _handle_agent_run(self) -> None:
        try:
            payload = self._read_json_body()
        except ValueError as exc:
            return self._json_error(str(exc), status=HTTPStatus.BAD_REQUEST)

        agent_id = str(payload.get("agent_id", "")).strip()
        input_json = payload.get("input_json", {}) or {}

        if not agent_id:
            return self._json_error("agent_id is required", status=HTTPStatus.BAD_REQUEST)
        if not isinstance(input_json, dict):
            return self._json_error("input_json must be an object", status=HTTPStatus.BAD_REQUEST)

        try:
            engine, agent_registry = _build_runtime()
            state = engine.run_to_completion(agent_name=agent_id, input_json=input_json)
            definition = agent_registry.get(agent_id)
        except KeyError as exc:
            return self._json_error(str(exc), status=HTTPStatus.NOT_FOUND)
        except Exception as exc:  # pylint: disable=broad-except
            return self._send_json(
                {
                    "agent_id": agent_id,
                    "run_id": None,
                    "finished": False,
                    "failed": True,
                    "error": str(exc),
                },
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

        history = self._serialize_history(state, definition)

        error_message = None
        if state.failed:
            for record in reversed(state.history):
                if record.error:
                    error_message = record.error
                    break

        payload = {
            "agent_id": agent_id,
            "run_id": state.run_id,
            "finished": bool(state.finished),
            "failed": bool(state.failed),
            "variables": self._truncate_value(state.variables),
            "steps": history,
        }

        if error_message:
            payload["error"] = error_message

        return self._send_json(payload)

    def _handle_agents_graph(self) -> None:
        agents_dir = self.agents_dir
        agents: Dict[str, Dict[str, object]] = {}
        definitions: Dict[str, AgentDefinition] = {}
        edges: List[Dict[str, object]] = []

        try:
            loader = AgentConfigLoader([str(agents_dir)])
            agent_files: List[Path] = []
            for pattern in ("*.yaml", "*.yml"):
                agent_files.extend(agents_dir.rglob(pattern))

            for path in sorted(agent_files, key=lambda p: str(p)):
                definition = loader.load_file(path)
                rel_path = str(path.relative_to(agents_dir))

                agent_entry = agents.setdefault(
                    definition.name,
                    {
                        "name": definition.name,
                        "description": definition.description,
                        "sources": [],
                    },
                )
                if not agent_entry.get("description") and definition.description:
                    agent_entry["description"] = definition.description
                agent_entry["sources"].append(rel_path)

                definitions[definition.name] = definition
        except Exception as exc:  # pylint: disable=broad-except
            return self._send_json(
                {"error": f"failed to load agents: {exc}"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

        for definition in definitions.values():
            for step_id, step in definition.steps.items():
                if step.tool_name == "agent_call":
                    target_agent = step.tool_params.get("agent_name") if step.tool_params else None
                    if target_agent:
                        edges.append(
                            {
                                "from": definition.name,
                                "to": str(target_agent),
                                "kind": "agent_call",
                                "step_id": step_id,
                                "tool_name": step.tool_name,
                            }
                        )
                if step.validator_agent_name:
                    edges.append(
                        {
                            "from": definition.name,
                            "to": step.validator_agent_name,
                            "kind": "validator",
                            "step_id": step_id,
                            "tool_name": step.tool_name,
                        }
                    )

        payload = {"agents": sorted(agents.values(), key=lambda a: a["name"]), "edges": edges}
        return self._send_json(payload)

    def _agent_path(self, agent_name: str) -> Path:
        safe_name = agent_name.replace("/", "_").replace("\\", "_")
        return self.agents_dir / f"{safe_name}.yaml"


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    static_dir = Path(__file__).parent / "static"
    os.chdir(static_dir)

    handler = AgentEditorHandler
    server = ThreadingHTTPServer((host, port), handler)
    bound_host, bound_port = server.server_address
    print(f"Serving web editor on http://{bound_host}:{bound_port}")
    print(f"Agents directory: {find_agents_dir()}")
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
