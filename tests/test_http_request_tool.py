import json
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from agentfw.core.models import AgentDefinition
from agentfw.core.state import AgentState, ExecutionContext
from agentfw.tools.builtin import HttpRequestTool


@dataclass
class NoOpEngine:
    pass


def make_context(variables: dict[str, object]) -> ExecutionContext:
    state = AgentState(run_id="r1", agent_name="agent", variables=variables)
    definition = AgentDefinition(name="agent")
    return ExecutionContext(definition=definition, state=state, engine=NoOpEngine())


class RecordingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/json"):
            body = json.dumps({"message": "hello"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/text"):
            body = b"plain response"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/error"):
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"server error")
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body_bytes = self.rfile.read(length)
        try:
            parsed_body = json.loads(body_bytes.decode() or "null")
        except json.JSONDecodeError:
            parsed_body = body_bytes.decode()

        response_body = json.dumps({"received": parsed_body}).encode()

        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(response_body)

    def log_message(self, format: str, *args):  # pragma: no cover - silence test output
        return


def start_server():
    server = HTTPServer(("localhost", 0), RecordingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, server.server_address[1]


def test_http_request_success_and_json_parsing():
    server, port = start_server()
    tool = HttpRequestTool()
    ctx = make_context({})

    try:
        result = tool.execute(ctx, {"url": f"http://localhost:{port}/json"})
    finally:
        server.shutdown()
        server.server_close()

    assert result["status_code"] == 200
    assert result["json"] == {"message": "hello"}
    assert "json_error" not in result
    assert "plain response" not in result["text"]


def test_http_request_raises_on_failure_when_not_allowed():
    server, port = start_server()
    tool = HttpRequestTool()
    ctx = make_context({})

    try:
        with pytest.raises(RuntimeError):
            tool.execute(ctx, {"url": f"http://localhost:{port}/error"})
    finally:
        server.shutdown()
        server.server_close()


def test_http_request_can_allow_failure_and_save_body():
    server, port = start_server()
    tool = HttpRequestTool()
    ctx = make_context({})

    try:
        result = tool.execute(
            ctx,
            {
                "url": f"http://localhost:{port}/error",
                "allow_failure": True,
                "save_body_var": "body",
            },
        )
    finally:
        server.shutdown()
        server.server_close()

    assert result["status_code"] == 500
    assert result["json"] is None
    assert "json_error" in result
    assert result["text"] == "server error"
    assert ctx.get_var("body") == "server error"


def test_http_request_posts_json_payload():
    server, port = start_server()
    tool = HttpRequestTool()
    ctx = make_context({})

    try:
        result = tool.execute(
            ctx,
            {
                "url": f"http://localhost:{port}/echo",
                "method": "POST",
                "json": {"foo": "bar"},
            },
        )
    finally:
        server.shutdown()
        server.server_close()

    assert result["status_code"] == 201
    assert result["json"] == {"received": {"foo": "bar"}}
