# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.types import DispatchResult, ExecutionContext
from core.memory import Memory


class Step:
    """Interface for a single step."""

    def execute(self, memory: Memory, ctx: ExecutionContext) -> DispatchResult:
        raise NotImplementedError


@dataclass
class StepLoop:
    """Repeat a step until it signals break_loop=True or max_iters reached."""

    inner: Step
    max_iters: int = 20
    hide_internal_from_history: bool = True

    def execute(self, memory: Memory, ctx: ExecutionContext) -> DispatchResult:
        current = memory
        last_res: Optional[DispatchResult] = None
        for i in range(self.max_iters):
            ctx.debug(f"[StepLoop] iter={i+1}/{self.max_iters}")
            res = self.inner.execute(current, ctx)
            last_res = res
            current = res.memory
            if res.break_loop:
                return res
        # didn't break
        if last_res is None:
            return DispatchResult(memory=current, break_loop=True)
        return DispatchResult(memory=current, user_output=last_res.user_output, break_loop=True)
