from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib import request

from agentfw.web.server import AgentEditorHandler


@contextmanager
def run_server(tmp_dir: Path):
    original_cwd = Path.cwd()
    server = None
    try:
        tmp_agents = tmp_dir / "agents"
        tmp_agents.mkdir(parents=True, exist_ok=True)
        # Change cwd so handler finds temp agents dir
        os.chdir(tmp_dir)
        server = ThreadingHTTPServer(("127.0.0.1", 0), AgentEditorHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        os.chdir(original_cwd)
        if server:
            try:
                server.shutdown()
            except Exception:
                pass


def test_run_endpoint_returns_state(tmp_path) -> None:
    with run_server(tmp_path) as base_url:
        payload = {
            "agent_id": "std.shell",
            "input_json": {"command": "echo hi"},
        }
        req = request.Request(
            f"{base_url}/api/agents/run",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
        data = json.loads(body)

        assert data["agent_id"] == "std.shell"
        assert "out" in data
        assert "trace" in data
