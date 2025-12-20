from __future__ import annotations

import pytest

from agentfw.web.server import AgentEditorHandler


def test_chat_send_rejects_blank_messages() -> None:
    with pytest.raises(ValueError):
        AgentEditorHandler._normalize_chat_message("", None)
    with pytest.raises(ValueError):
        AgentEditorHandler._normalize_chat_message("   ", "conv")
    with pytest.raises(ValueError):
        AgentEditorHandler._normalize_chat_message(None, "conv")  # type: ignore[arg-type]
