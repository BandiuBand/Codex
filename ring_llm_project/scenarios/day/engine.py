from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ring_llm_project.commands.registry import CommandRegistry
from ring_llm_project.core.normalize import Normalizer, NormalizeConfig
from ring_llm_project.core.parse_cmd import CommandParser
from ring_llm_project.core.router import LLMRouter
from ring_llm_project.core.step_loop import StepLoop, StepLoopConfig
from ring_llm_project.core.types import DispatchResult, ExecutionContext
from ring_llm_project.core.validate import CommandValidator, ValidateConfig

from .s2_fold_loop import FoldLoopParams, S2FoldLoopStep


@dataclass(frozen=True)
class DayEngineConfig:
    llm_key: str = "oss20b"
    max_body_chars: int = 9000
    max_iters: int = 12


class DayEngine:
    def __init__(
        self,
        router: LLMRouter,
        registry: CommandRegistry,
        cfg: Optional[DayEngineConfig] = None,
    ) -> None:
        self.cfg = cfg or DayEngineConfig()
        self.router = router
        self.registry = registry

        normalizer = Normalizer(NormalizeConfig(strip_thoughts_only_if_prefix=True))
        validator = CommandValidator(ValidateConfig(mode="extract_anywhere"))
        parser = CommandParser()

        s2_params = FoldLoopParams(
            llm_key=self.cfg.llm_key,
            max_body_chars=self.cfg.max_body_chars,
        )
        s2_step = S2FoldLoopStep(
            router=self.router,
            registry=self.registry,
            normalizer=normalizer,
            validator=validator,
            parser=parser,
            params=s2_params,
        )

        self.s2_loop = StepLoop(
            inner_step=s2_step,
            cfg=StepLoopConfig(max_iters=self.cfg.max_iters),
            name="S2FoldLoop",
        )

    def run_s2(self, memory, ctx: Optional[ExecutionContext] = None) -> DispatchResult:
        res = self.s2_loop.execute(memory, ctx)
        if isinstance(res, DispatchResult):
            return res
        return DispatchResult(memory=res)
