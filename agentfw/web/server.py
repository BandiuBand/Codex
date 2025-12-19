from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List

from agentfw.core.agent_spec import agent_spec_from_dict, agent_spec_to_dict
from agentfw.io.agent_yaml import load_agent_spec, save_agent_spec
from agentfw.llm.base import DummyLLMClient, OllamaLLMClient
from agentfw.runtime.engine import AgentRepository, ExecutionEngine


class AgentEditorHandler(SimpleHTTPRequestHandler):
    server_version = "AgentEditor/agents"

    def __init__(self, *args, **kwargs):
        self.static_dir = Path(__file__).parent / "static"
        self.agents_dir = self._find_agents_dir()
        self.repository = AgentRepository(self.agents_dir)
        self.engine = ExecutionEngine(
            repository=self.repository,
            llm_client=OllamaLLMClient(),
            llm_client_factory=self._build_llm_factory(),
        )
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
        if self.path.startswith("/api/agent/"):
            return self._handle_get_agent()
        if self.path == "/run":
            self.path = "/run.html"
        if self.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if self.path.startswith("/api/agent/"):
            return self._handle_save_agent()
        if self.path.startswith("/api/run/"):
            return self._handle_run_agent()
        if self.path.startswith("/api/agents/") and self.path.endswith("/run"):
            return self._handle_run_agent(compat=True)
        return self._json_error("Невідомий маршрут", status=HTTPStatus.NOT_FOUND)

    # Helpers
    def _read_json(self) -> Dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:  # pragma: no cover - client error path
            raise ValueError(f"Некоректний JSON: {exc}") from exc

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
        return env / "agents"

    @staticmethod
    def _build_llm_factory():  # pragma: no cover - simple wiring
        """Return an LLM client factory based on the configured mode.

        By default we now prioritize real Ollama calls so the API behaves as
        expected out of the box. To keep the previous mocked behavior, set the
        environment variable ``AGENTFW_WEB_LLM_MODE`` to ``dummy``.
        """

        mode = (os.getenv("AGENTFW_WEB_LLM_MODE") or "ollama").lower()
        if mode == "dummy":
            return lambda host, model: DummyLLMClient(prefix=f"LLM({model})@{host}: ")
        return lambda host, model: OllamaLLMClient(base_url=host, model=model or "")

    # API
    def _handle_list_agents(self) -> None:
        agents: List[Dict[str, object]] = []
        for spec in self.repository.list():
            agents.append(
                {
                    "name": spec.name,
                    "title_ua": spec.title_ua,
                    "kind": spec.kind,
                    "inputs": [v.name for v in spec.inputs],
                    "outputs": [v.name for v in spec.outputs],
                    "locals": [v.name for v in spec.locals],
                }
            )
        self._send_json(agents)

    def _handle_get_agent(self) -> None:
        name = self.path.split("/api/agent/")[-1]
        if not name:
            return self._json_error("Потрібна назва агента", status=HTTPStatus.BAD_REQUEST)
        try:
            spec = load_agent_spec(self.agents_dir / f"{name}.yaml")
        except Exception as exc:  # noqa: BLE001
            return self._json_error(str(exc), status=HTTPStatus.NOT_FOUND)
        return self._send_json(agent_spec_to_dict(spec))

    def _handle_save_agent(self) -> None:
        name = self.path.split("/api/agent/")[-1]
        try:
            raw = self._read_json()
            raw["name"] = name
            spec = agent_spec_from_dict(raw)
        except Exception as exc:  # noqa: BLE001
            return self._json_error(str(exc), status=HTTPStatus.BAD_REQUEST)
        try:
            save_agent_spec(self.agents_dir / f"{name}.yaml", spec)
        except Exception as exc:  # noqa: BLE001
            return self._json_error(str(exc), status=HTTPStatus.INTERNAL_SERVER_ERROR)
        self._send_json({"ok": True})

    def _handle_run_agent(self, compat: bool = False) -> None:
        if compat:
            parts = [p for p in self.path.split("/") if p]
            agent_name = parts[2] if len(parts) >= 3 else ""
        else:
            agent_name = self.path.split("/api/run/")[-1]
        try:
            payload = self._read_json()
        except ValueError as exc:
            return self._json_error(str(exc), status=HTTPStatus.BAD_REQUEST)
        input_json = payload.get("input") or payload.get("input_json") or {}
        if isinstance(input_json, dict) and "task" in input_json and "завдання" not in input_json:
            input_json = dict(input_json)
            input_json["завдання"] = input_json.get("task")
        if not isinstance(input_json, dict):
            return self._json_error("input має бути об’єктом", status=HTTPStatus.BAD_REQUEST)
        if not agent_name:
            return self._json_error("Назва агента обов’язкова", status=HTTPStatus.BAD_REQUEST)
        try:
            state = self.engine.run_to_completion(agent_name, input_json=input_json)
        except Exception as exc:  # noqa: BLE001
            return self._send_json({"ok": False, "vars": {}, "log": [], "error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
        payload = {"ok": True, "vars": state.vars, "log": state.trace, "error": None, "run_id": state.run_id}
        return self._send_json(payload)


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    handler = AgentEditorHandler
    server = ThreadingHTTPServer((host, port), handler)
    bound_host, bound_port = server.server_address
    print(f"Serving web editor on http://{bound_host}:{bound_port}")
    print(f"Agents directory: {handler._find_agents_dir()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover - manual shutdown
        server.server_close()


__all__ = ["run_server", "AgentEditorHandler"]
