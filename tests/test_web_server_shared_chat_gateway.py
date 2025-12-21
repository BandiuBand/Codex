import io

from agentfw.runtime.chat_agent import ChatAgentGateway
from agentfw.web.server import AgentEditorHandler


class DummySocket:
    def makefile(self, *args, **kwargs):  # noqa: D401
        """Return a BytesIO handle to satisfy BaseHTTPRequestHandler."""

        return io.BytesIO()


class DummyServer:
    def __init__(self) -> None:
        self.server_address = ("127.0.0.1", 0)


class NoopHandler(AgentEditorHandler):
    def setup(self) -> None:  # type: ignore[override]
        self.rfile = io.BytesIO()
        self.wfile = io.BytesIO()

    def handle(self) -> None:  # type: ignore[override]
        return None

    def finish(self) -> None:  # type: ignore[override]
        return None


def test_chat_gateway_shared_between_requests() -> None:
    AgentEditorHandler._shared_chat_agent = ChatAgentGateway()
    AgentEditorHandler._shared_engine = None

    first = NoopHandler(DummySocket(), ("127.0.0.1", 0), DummyServer())
    first.chat_agent.post_agent("AdaptiveAgent", "Привіт, дай задачу")

    second = NoopHandler(DummySocket(), ("127.0.0.1", 0), DummyServer())

    history = [msg.text for msg in second.chat_agent.history()]
    assert history[-1] == "Привіт, дай задачу"


def test_engine_uses_shared_chat_gateway() -> None:
    AgentEditorHandler._shared_chat_agent = ChatAgentGateway()
    AgentEditorHandler._shared_engine = None

    handler = NoopHandler(DummySocket(), ("127.0.0.1", 0), DummyServer())

    assert handler.engine.chat_gateway is handler.chat_agent
