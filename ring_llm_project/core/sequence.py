from __future__ import annotations

from typing import Any, List, Optional

from core.types import DispatchResult, ExecutionContext
from .memory import Memory
from .step import Step, clear_stop, should_stop


class StepSequence:
    """
    Deterministic ordered steps, no loops.
    """

    def __init__(self, steps: List[Step], developer_notes: str = "") -> None:
        self.steps = list(steps)
        self.developer_notes = developer_notes

    def run(self, memory: Any, ctx: Optional[ExecutionContext] = None) -> Any:
        current = memory
        if isinstance(current, Memory):
            clear_stop(current)
        for step in self.steps:
            res = step.execute(current, ctx)
            if isinstance(res, DispatchResult):
                current = res.memory
            else:
                current = res
            if isinstance(current, Memory) and should_stop(current):
                break
        return current
