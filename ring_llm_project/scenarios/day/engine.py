# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass

from core.dispatcher import CommandDispatcher
from core.llm_client import LLMClient
from core.memory import Memory
from core.step_loop import StepLoop
from core.types import DispatchResult, ExecutionContext
from scenarios.day.s2_fold_loop import S2FoldLoopStep


@dataclass
class DayEngine:
    dispatcher: CommandDispatcher
    llm: LLMClient

    def run_s2_fold_loop(self, memory: Memory, ctx: ExecutionContext, max_iters: int = 50) -> DispatchResult:
        inner = S2FoldLoopStep(dispatcher=self.dispatcher, llm=self.llm)
        loop = StepLoop(inner_step=inner, max_iters=max_iters)
        return loop.execute(memory, ctx)
