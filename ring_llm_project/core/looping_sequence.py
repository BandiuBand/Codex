from __future__ import annotations

from typing import Any, List, Optional

from core.sequence import Step
from core.types import ExecutionContext, DispatchResult


class LoopingStepSequence:
    """
    Sequence that can loop over a fixed list of steps until it receives LOOP DONE signal.

    Key properties:
      - It loops over 'loop_steps' repeatedly.
      - It stops immediately when any step returns DispatchResult(loop_done=True).
      - It DOES NOT require CLI.
      - It DOES NOT enforce how steps are implemented (LLM-based or not).
      - You can make the loop "invisible" by ensuring steps do not write extra noise to memory,
        and by making LOOP DONE itself visible_event=False (already done).
    """

    def __init__(
        self,
        loop_steps: List[Step],
        developer_notes: str = "",
        max_iterations: int = 25,
        on_max_iterations: str = "stop",  # "stop" | "raise"
    ) -> None:
        if max_iterations < 1:
            raise ValueError("max_iterations must be >= 1")

        if on_max_iterations not in ("stop", "raise"):
            raise ValueError("on_max_iterations must be 'stop' or 'raise'")

        self.loop_steps = list(loop_steps)
        self.developer_notes = developer_notes
        self.max_iterations = max_iterations
        self.on_max_iterations = on_max_iterations

    def run(self, memory: Any, ctx: ExecutionContext) -> Any:
        last_res: Optional[DispatchResult] = None

        for it in range(1, self.max_iterations + 1):
            for step in self.loop_steps:
                res = step.execute(memory, ctx)
                last_res = res
                memory = res.memory

                # Stop condition: LOOP DONE command (or step decided loop_done)
                if res.loop_done:
                    return memory

        # If still not done after max_iterations
        if self.on_max_iterations == "raise":
            note = last_res.debug_note if last_res else None
            raise RuntimeError(f"Loop did not finish within max_iterations={self.max_iterations}. Last: {note}")

        return memory
