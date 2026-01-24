from __future__ import annotations

from typing import Optional

from ring_llm_project.commands.base import IOAdapter
from ring_llm_project.commands.registry import CommandRegistry

from .behavior import (
    BehaviorModel,
    CommandBlockStep,
    CommandDispatchStep,
    DebugFlags,
    FoldStep,
    NormalizeStep,
    PromptAndCallStep,
)
from .fold import Folder
from .normalize import Normalizer, NormalizeConfig
from .parse_cmd import CommandParser
from .process import ProcessConfig
from .prompt_builder import PromptBuilder, PromptConfig
from .router import LLMRouter
from .sequence import StepSequence
from .validate import CommandValidator, ValidateConfig


class ConsciousnessBuilder:
    def __init__(
        self,
        cfg: ProcessConfig,
        router: LLMRouter,
        registry: CommandRegistry,
        io: Optional[IOAdapter] = None,
        debug: DebugFlags = DebugFlags(),
    ):
        self.cfg = cfg
        self.router = router
        self.registry = registry
        self.io = io
        self.debug = debug

    def build(self) -> BehaviorModel:
        folder = Folder(keep_last_events=self.cfg.auto_fold_keep_last_events)
        normalizer = Normalizer(NormalizeConfig(strip_thoughts_only_if_prefix=True))
        validator = CommandValidator(ValidateConfig(mode="extract_anywhere"))
        parser = CommandParser()
        prompt_builder = PromptBuilder(
            PromptConfig(),
            registry=self.registry,
            validator_help=validator.format_help_prompt(),
        )

        sequence = StepSequence(
            steps=[
                FoldStep(folder=folder, debug=self.debug),
                PromptAndCallStep(
                    prompt_builder=prompt_builder,
                    router=self.router,
                    control_llm_key=self.cfg.control_llm_key,
                    debug=self.debug,
                ),
                NormalizeStep(normalizer=normalizer),
                CommandBlockStep(validator=validator, io=self.io, debug=self.debug),
                CommandDispatchStep(
                    parser=parser,
                    registry=self.registry,
                    router=self.router,
                    io=self.io,
                ),
            ]
        )
        return BehaviorModel(sequence=sequence)

    def load(self) -> BehaviorModel:
        return self.build()
