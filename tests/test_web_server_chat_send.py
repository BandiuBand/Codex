from __future__ import annotations

import pytest

from agentfw.web.server import AgentEditorHandler


def test_chat_send_allows_blank_on_new_conversation() -> None:
    assert AgentEditorHandler._normalize_chat_message("", None) == ""
    assert AgentEditorHandler._normalize_chat_message("   ", None) == ""


def test_chat_send_rejects_blank_for_existing_conversation() -> None:
    with pytest.raises(ValueError):
        AgentEditorHandler._normalize_chat_message("   ", "conv")
    with pytest.raises(ValueError):
        AgentEditorHandler._normalize_chat_message(None, "conv")  # type: ignore[arg-type]
