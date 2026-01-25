from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .step import Step
from .types import DispatchResult, ExecutionContext


@dataclass(frozen=True)
class StepLoopConfig:
    max_iters: int = 12
    invisible: bool = True


class StepLoop(Step):
    """
    Repeat an inner step until it signals loop_done=True or max_iters is reached.

    Loop control is intended to be invisible: the loop itself should not emit
    extra memory/history noise, and LOOP DONE should be invisible.
    """

    def __init__(
        self,
        inner_step: Step,
        cfg: Optional[StepLoopConfig] = None,
        name: str = "StepLoop",
    ) -> None:
        self.inner_step = inner_step
        self.cfg = cfg or StepLoopConfig()
        self.name = name

    def execute(self, memory, ctx: Optional[ExecutionContext] = None):
        current = memory
        last_user_output = None

        for i in range(1, self.cfg.max_iters + 1):
            res = self.inner_step.execute(current, ctx)

            if isinstance(res, DispatchResult):
                current = res.memory
                if res.user_output:
                    last_user_output = res.user_output
                if res.loop_done:
                    return DispatchResult(
                        memory=current,
                        loop_done=True,
                        visible_event=res.visible_event,
                        user_output=last_user_output,
                        user_message=res.user_message,
                        stop_for_user_input=res.stop_for_user_input,
                        debug_note=res.debug_note or f"{self.name} done after {i} iteration(s).",
                    )
                if res.stop_for_user_input:
                    return DispatchResult(
                        memory=current,
                        loop_done=False,
                        visible_event=res.visible_event,
                        user_output=last_user_output,
                        user_message=res.user_message,
                        stop_for_user_input=True,
                        debug_note=res.debug_note or f"{self.name} stopped for user input.",
                    )
            else:
                current = res

        return DispatchResult(
            memory=current,
            loop_done=False,
            visible_event=False,
            user_output=last_user_output,
            debug_note=f"{self.name} exceeded max_iters={self.cfg.max_iters}.",
        )
