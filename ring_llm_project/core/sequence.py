from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .memory import Memory
from .step import Step, clear_stop, should_stop


@dataclass
class StepSequence:
    steps: List[Step] = field(default_factory=list)

    def run(self, memory: Memory) -> Memory:
        current = memory
        clear_stop(current)
        for step in self.steps:
            current = step.execute(current)
            if should_stop(current):
                break
        return current
