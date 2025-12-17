from __future__ import annotations

import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List

from agentfw.core.agent import Agent
from agentfw.io.agent_yaml import agent_from_dict, load_agent, save_agent
from agentfw.runtime.builtins import BUILTIN_PORTS, build_default_registry
from agentfw.runtime.engine import AgentRepository, ExecutionEngine


class AgentEditorHandler(SimpleHTTPRequestHandler):
    server_version = "AgentEditor/lanes"

    def __init__(self, *args, **kwargs):
        self.static_dir = Path(__file__).parent / "static"
        self.agents_dir = self._find_agents_dir()
        self.repository = AgentRepository(self.agents_dir)
        self.builtin_registry = build_default_registry()
        self.engine = ExecutionEngine(repository=self.repository, builtin_registry=self.builtin_registry)
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
        if self.path == "/api/agents":
            return self._handle_list_agents()
        if self.path.startswith("/api/agents/"):
            return self._handle_get_agent()
        if self.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_PUT(self) -> None:  # noqa: N802
        if self.path.startswith("/api/agents/"):
            return self._handle_put_agent()
        return self._json_error("Unknown endpoint", status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/agents/run":
            return self._handle_run_agent()
        return self._json_error("Unknown endpoint", status=HTTPStatus.NOT_FOUND)

    # Helpers
    def _read_json(self) -> Dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}") from exc

    def _send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json_error(self, message: str, status: HTTPStatus) -> None:
        self._send_json({"ok": False, "error": message}, status=status)

    @staticmethod
    def _find_agents_dir() -> Path:
        env = Path.cwd()
        for parent in [env] + list(env.parents):
            candidate = parent / "agents"
            if candidate.exists() and candidate.is_dir():
                return candidate
        return Path.cwd() / "agents"

    # API handlers
    def _handle_list_agents(self) -> None:
        agents: List[Dict[str, str]] = []
        if self.agents_dir.exists():
            for agent in self.repository.list():
                agents.append({"id": agent.id, "name": agent.name})
        for builtin_id in sorted(self.builtin_registry.registry.keys()):
            agents.append({"id": builtin_id, "name": builtin_id})
        seen: Dict[str, str] = {}
        uniq: List[Dict[str, str]] = []
        for entry in agents:
            if entry["id"] in seen:
                continue
            seen[entry["id"]] = entry["name"]
            uniq.append(entry)
        uniq.sort(key=lambda a: a["id"])
        self._send_json({"agents": uniq})

    def _handle_get_agent(self) -> None:
        agent_id = self.path.split("/api/agents/")[-1]
        if not agent_id:
            return self._json_error("agent_id is required", status=HTTPStatus.BAD_REQUEST)

        if self.builtin_registry.has(agent_id):
            ports = BUILTIN_PORTS.get(agent_id, {})
            agent = Agent(
                id=agent_id,
                name=agent_id,
                description=None,
                inputs=ports.get("inputs", []),
                locals=[],
                outputs=ports.get("outputs", []),
                children={},
                lanes=[],
                links=[],
            )
        else:
            try:
                agent = self.repository.get(agent_id)
            except KeyError:
                return self._json_error("agent not found", status=HTTPStatus.NOT_FOUND)

        payload = {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "inputs": [vars(v) for v in agent.inputs],
            "locals": [vars(v) for v in agent.locals],
            "outputs": [vars(v) for v in agent.outputs],
            "children": {cid: vars(c) for cid, c in agent.children.items()},
            "lanes": [vars(lane) for lane in agent.lanes],
            "links": [vars(link) for link in agent.links],
        }
        return self._send_json(payload)

    def _handle_put_agent(self) -> None:
        agent_id = self.path.split("/api/agents/")[-1]
        if not agent_id:
            return self._json_error("agent_id is required", status=HTTPStatus.BAD_REQUEST)
        try:
            payload = self._read_json()
            payload["id"] = agent_id
            agent = agent_from_dict(payload)
        except Exception as exc:  # noqa: BLE001
            return self._json_error(str(exc), status=HTTPStatus.BAD_REQUEST)

        try:
            save_agent(self.agents_dir / f"{agent_id}.yaml", agent)
        except Exception as exc:  # noqa: BLE001
            return self._json_error(str(exc), status=HTTPStatus.INTERNAL_SERVER_ERROR)

        return self._send_json({"ok": True})

    def _handle_run_agent(self) -> None:
        try:
            payload = self._read_json()
        except ValueError as exc:
            return self._json_error(str(exc), status=HTTPStatus.BAD_REQUEST)

        agent_id = str(payload.get("agent_id", "")).strip()
        input_json = payload.get("input_json", {}) or {}
        locals_json = payload.get("locals_json", {}) or {}

        if not agent_id:
            return self._json_error("agent_id is required", status=HTTPStatus.BAD_REQUEST)
        if not isinstance(input_json, dict):
            return self._json_error("input_json must be an object", status=HTTPStatus.BAD_REQUEST)
        if not isinstance(locals_json, dict):
            return self._json_error("locals_json must be an object", status=HTTPStatus.BAD_REQUEST)

        try:
            state = self.engine.run_to_completion(agent_id, input_json, locals_json)
        except Exception as exc:  # noqa: BLE001
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

        payload = {
            "agent_id": state.agent_id,
            "run_id": state.run_id,
            "finished": state.finished,
            "failed": state.failed,
            "out": state.out,
            "locals": state.locals,
            "trace": state.trace.entries,
        }
        return self._send_json(payload)


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    handler = AgentEditorHandler
    server = ThreadingHTTPServer((host, port), handler)
    bound_host, bound_port = server.server_address
    print(f"Serving web editor on http://{bound_host}:{bound_port}")
    print(f"Agents directory: {handler._find_agents_dir()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


__all__ = ["run_server"]
