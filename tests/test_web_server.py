import json
import os
import shutil
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Dict

import yaml

from agentfw.web.server import AgentEditorHandler, _find_agents_dir


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

    def test_agents_graph_includes_sources_and_step_metadata(self) -> None:
        agents_dir = _find_agents_dir()
        temp_dir = agents_dir / "tmp_graph_tests"
        nested_dir = temp_dir / "nested"
        nested_dir.mkdir(parents=True, exist_ok=True)

        parent_agent = {
            "name": "graph_parent",
            "entry_step_id": "start",
            "end_step_ids": ["done"],
            "steps": {
                "start": {
                    "name": "start",
                    "kind": "tool",
                    "tool_name": "agent_call",
                    "tool_params": {"agent_name": "graph_child"},
                    "save_mapping": {},
                    "validator_agent_name": None,
                    "validator_params": {},
                    "validator_policy": {},
                    "transitions": [
                        {"target_step_id": "done", "condition": {"type": "always"}},
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

        child_agent = {
            "name": "graph_child",
            "entry_step_id": "validate",
            "end_step_ids": ["validate"],
            "steps": {
                "validate": {
                    "name": "validate",
                    "kind": "validator",
                    "tool_params": {},
                    "save_mapping": {},
                    "validator_agent_name": "simple_demo_agent",
                    "validator_params": {},
                    "validator_policy": {},
                    "transitions": [],
                }
            },
        }

        duplicate_child = {
            "name": "graph_child",
            "entry_step_id": "validate",
            "end_step_ids": ["validate"],
            "steps": {
                "validate": {
                    "name": "validate",
                    "kind": "validator",
                    "tool_params": {},
                    "save_mapping": {},
                    "validator_agent_name": None,
                    "validator_params": {},
                    "validator_policy": {},
                    "transitions": [],
                }
            },
        }

        parent_path = temp_dir / "graph_parent.yaml"
        child_path = nested_dir / "graph_child.yaml"
        duplicate_path = temp_dir / "graph_child_duplicate.yaml"

        try:
            parent_path.write_text(yaml.safe_dump(parent_agent))
            child_path.write_text(yaml.safe_dump(child_agent))
            duplicate_path.write_text(yaml.safe_dump(duplicate_child))

            graph_resp = self._request("GET", "/api/agents_graph")
            assert graph_resp["status"] == 200

            graph = graph_resp["json"]
            assert "agents" in graph and "edges" in graph

            parent = next(a for a in graph["agents"] if a["name"] == "graph_parent")
            child = next(a for a in graph["agents"] if a["name"] == "graph_child")

            assert str(parent_path.relative_to(agents_dir)) in parent.get("sources", [])
            assert str(child_path.relative_to(agents_dir)) in child.get("sources", [])
            assert str(duplicate_path.relative_to(agents_dir)) in child.get("sources", [])

            edges = [e for e in graph["edges"] if e["from"] in {"graph_parent", "graph_child"}]
            assert any(
                e["kind"] == "agent_call"
                and e["from"] == "graph_parent"
                and e["to"] == "graph_child"
                and e.get("step_id") == "start"
                and e.get("tool_name") == "agent_call"
                for e in edges
            )
            assert any(
                e["kind"] == "validator"
                and e["from"] == "graph_child"
                and e["to"] == "simple_demo_agent"
                and e.get("step_id") == "validate"
                for e in edges
            )
        finally:
            shutil.rmtree(temp_dir)
