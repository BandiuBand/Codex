from __future__ import annotations

from unittest.mock import Mock, patch

from agentfw.llm.base import OllamaLLMClient


def _mock_response(text: str) -> Mock:
    resp = Mock()
    resp.status_code = 200
    resp.json.return_value = {"response": text}
    return resp


def test_ollama_default_timeout_and_payload() -> None:
    client = OllamaLLMClient(base_url="http://example:1234", model="qwen3:32b")
    response = _mock_response("hello")
    with patch("agentfw.llm.base.requests.post", return_value=response) as post:
        result = client.generate("ping", temperature=0.1)

    assert result == "hello"
    post.assert_called_once()
    _, kwargs = post.call_args
    assert kwargs["timeout"] == client.timeout
    assert kwargs["json"]["model"] == "qwen3:32b"
    assert kwargs["json"]["prompt"] == "ping"
    assert kwargs["json"]["temperature"] == 0.1
    assert "timeout" not in kwargs["json"]


def test_ollama_timeout_override_and_cleanup() -> None:
    client = OllamaLLMClient(base_url="http://example:1234", model="qwen3:32b", timeout=5)
    response = _mock_response("hello")
    with patch("agentfw.llm.base.requests.post", return_value=response) as post:
        result = client.generate("ping", temperature=0, timeout=321)

    assert result == "hello"
    _, kwargs = post.call_args
    assert kwargs["timeout"] == 321.0
    assert "timeout" not in kwargs["json"]
