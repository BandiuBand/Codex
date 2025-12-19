from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

Role = Literal["user", "chat", "agent", "tool"]
Status = Literal["ok", "blocked", "error"]
ExpectedOutput = Literal["final", "question", "plan", "tool_call", "file_written"]
SecurityMode = Literal["safe", "restricted", "dev"]


@dataclass
class AgentEnvelope:
    """Стандартизований формат повідомлень між агентами."""

    conversation_id: str
    message_id: str
    role: Role
    timestamp: float
    content: str
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    tooling_state: Optional[Dict[str, Any]] = None
    available_agents: Optional[List[str]] = None
    project_root: Optional[str] = None
    security_mode: Optional[SecurityMode] = None
    expected_output: Optional[ExpectedOutput] = None
    status: Optional[Status] = None
    missing_inputs: Optional[List[str]] = None
    questions_to_user: Optional[List[str]] = None
    why_blocked: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
            "role": self.role,
            "timestamp": self.timestamp,
            "content": self.content,
            "attachments": list(self.attachments),
            "tooling_state": self.tooling_state,
            "available_agents": self.available_agents,
            "project_root": self.project_root,
            "security_mode": self.security_mode,
            "expected_output": self.expected_output,
            "status": self.status,
            "missing_inputs": self.missing_inputs,
            "questions_to_user": self.questions_to_user,
            "why_blocked": self.why_blocked,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AgentEnvelope":
        cls._validate_role(payload.get("role"))
        cls._validate_status(payload.get("status"))
        cls._validate_expected_output(payload.get("expected_output"))
        timestamp = payload.get("timestamp")
        if timestamp is None:
            timestamp = time.time()
        return cls(
            conversation_id=str(payload.get("conversation_id", "")),
            message_id=str(payload.get("message_id", "")),
            role=payload.get("role"),
            timestamp=float(timestamp),
            content=str(payload.get("content", "")),
            attachments=list(payload.get("attachments") or []),
            tooling_state=payload.get("tooling_state"),
            available_agents=payload.get("available_agents"),
            project_root=payload.get("project_root"),
            security_mode=payload.get("security_mode"),
            expected_output=payload.get("expected_output"),
            status=payload.get("status"),
            missing_inputs=payload.get("missing_inputs"),
            questions_to_user=payload.get("questions_to_user"),
            why_blocked=payload.get("why_blocked"),
        )

    @staticmethod
    def _validate_role(role: Optional[str]) -> None:
        if role is None:
            raise ValueError("role is required for AgentEnvelope")
        if role not in {"user", "chat", "agent", "tool"}:
            raise ValueError(f"invalid role '{role}'")

    @staticmethod
    def _validate_status(status: Optional[str]) -> None:
        if status is None:
            return
        if status not in {"ok", "blocked", "error"}:
            raise ValueError(f"invalid status '{status}'")

    @staticmethod
    def _validate_expected_output(expected: Optional[str]) -> None:
        if expected is None:
            return
        if expected not in {"final", "question", "plan", "tool_call", "file_written"}:
            raise ValueError(f"invalid expected_output '{expected}'")


__all__ = ["AgentEnvelope", "Role", "Status", "ExpectedOutput", "SecurityMode"]
