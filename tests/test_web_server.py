import json
import os
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Dict

from agentfw.web.server import AgentEditorHandler


class TestWebServerIntegration:
    def setup_method(self) -> None:
        self.original_cwd = os.getcwd()
        self.static_dir = Path(__file__).resolve().parents[1] / "agentfw" / "web" / "static"
        os.chdir(self.static_dir)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), AgentEditorHandler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def teardown_method(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=2)
        os.chdir(self.original_cwd)

    def _request(self, method: str, path: str, body: Dict | None = None) -> Dict:
        conn = HTTPConnection("127.0.0.1", self.port)
        payload = None
        headers = {}
        if body is not None:
            payload = json.dumps(body)
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=payload, headers=headers)
        response = conn.getresponse()
        data = response.read().decode("utf-8")
        conn.close()
        return {"status": response.status, "json": json.loads(data)}

    def test_tools_and_validate_endpoints(self) -> None:
        tools_resp = self._request("GET", "/api/tools")
        assert tools_resp["status"] == 200
        assert isinstance(tools_resp["json"].get("tools"), list)
        assert tools_resp["json"]["tools"]
        assert isinstance(tools_resp["json"].get("conditions"), list)

        agents_resp = self._request("GET", "/api/agents")
        assert agents_resp["status"] == 200
        assert "agents" in agents_resp["json"]
        assert "simple_demo_agent" in agents_resp["json"]["agents"]

        minimal_agent = {
            "name": "integration_agent",
            "entry_step_id": "init",
            "end_step_ids": ["done"],
            "steps": {
                "init": {
                    "name": "init",
                    "kind": "tool",
                    "tool_name": "echo",
                    "tool_params": {"text": "hi"},
                    "save_mapping": {},
                    "validator_agent_name": None,
                    "validator_params": {},
                    "validator_policy": {},
                    "transitions": [
                        {
                            "target_step_id": "done",
                            "condition": {"type": "always"},
                        }
                    ],
                },
                "done": {
                    "name": "done",
                    "kind": "end",
                    "tool_params": {},
                    "save_mapping": {},
                    "validator_agent_name": None,
                    "validator_params": {},
                    "validator_policy": {},
                    "transitions": [],
                },
            },
        }

        validate_resp = self._request("POST", "/api/agents/validate", body=minimal_agent)
        assert validate_resp["status"] == 200
        assert validate_resp["json"].get("ok") is True
