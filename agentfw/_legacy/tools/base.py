from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict

from agentfw.core.state import ExecutionContext


class BaseTool(ABC):
    """Abstract base class for executable tools."""

    @abstractmethod
    def execute(self, ctx: ExecutionContext, params: Dict[str, object]) -> Dict[str, object]:
        """Execute the tool using the provided context and parameters."""
        raise NotImplementedError()
